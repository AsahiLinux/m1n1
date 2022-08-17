/* SPDX-License-Identifier: MIT */

/*
 * Useful references:
 * - TI KeyStone II Architecture Universal Serial Bus 3.0 (USB 3.0) User's Guide
 *   Literature Number: SPRUHJ7A, https://www.ti.com/lit/ug/spruhj7a/spruhj7a.pdf
 * - https://www.beyondlogic.org/usbnutshell/usb1.shtml
 */

#include "../build/build_tag.h"

#include "usb_dwc3.h"
#include "dart.h"
#include "malloc.h"
#include "memory.h"
#include "ringbuffer.h"
#include "string.h"
#include "types.h"
#include "usb_dwc3_regs.h"
#include "usb_types.h"
#include "utils.h"

#define MAX_ENDPOINTS   16
#define CDC_BUFFER_SIZE SZ_1M

#define usb_debug_printf(fmt, ...) debug_printf("usb-dwc3@%lx: " fmt, dev->regs, ##__VA_ARGS__)

#define STRING_DESCRIPTOR_LANGUAGES    0
#define STRING_DESCRIPTOR_MANUFACTURER 1
#define STRING_DESCRIPTOR_PRODUCT      2
#define STRING_DESCRIPTOR_SERIAL       3

#define CDC_DEVICE_CLASS 0x02

#define CDC_USB_VID 0x1209
#define CDC_USB_PID 0x316d

#define CDC_INTERFACE_CLASS         0x02
#define CDC_INTERFACE_CLASS_DATA    0x0a
#define CDC_INTERFACE_SUBCLASS_ACM  0x02
#define CDC_INTERFACE_PROTOCOL_NONE 0x00
#define CDC_INTERFACE_PROTOCOL_AT   0x01

#define DWC3_SCRATCHPAD_SIZE SZ_16K
#define TRB_BUFFER_SIZE      SZ_16K
#define XFER_BUFFER_SIZE     (SZ_16K * MAX_ENDPOINTS * 2)
#define PAD_BUFFER_SIZE      SZ_16K

#define TRBS_PER_EP              (TRB_BUFFER_SIZE / (MAX_ENDPOINTS * sizeof(struct dwc3_trb)))
#define XFER_BUFFER_BYTES_PER_EP (XFER_BUFFER_SIZE / MAX_ENDPOINTS)

#define XFER_SIZE SZ_16K

#define SCRATCHPAD_IOVA   0xbeef0000
#define EVENT_BUFFER_IOVA 0xdead0000
#define XFER_BUFFER_IOVA  0xbabe0000
#define TRB_BUFFER_IOVA   0xf00d0000

/* these map to the control endpoint 0x00/0x80 */
#define USB_LEP_CTRL_OUT 0
#define USB_LEP_CTRL_IN  1

/* maps to interrupt endpoint 0x81 */
#define USB_LEP_CDC_INTR_IN 3

/* these map to physical endpoints 0x02 and 0x82 */
#define USB_LEP_CDC_BULK_OUT 4
#define USB_LEP_CDC_BULK_IN  5

/* maps to interrupt endpoint 0x83 */
#define USB_LEP_CDC_INTR_IN_2 7

/* these map to physical endpoints 0x04 and 0x84 */
#define USB_LEP_CDC_BULK_OUT_2 8
#define USB_LEP_CDC_BULK_IN_2  9

/* content doesn't matter at all, this is the setting linux writes by default */
static const u8 cdc_default_line_coding[] = {0x80, 0x25, 0x00, 0x00, 0x00, 0x00, 0x08};

enum ep0_state {
    USB_DWC3_EP0_STATE_IDLE,
    USB_DWC3_EP0_STATE_SETUP_HANDLE,
    USB_DWC3_EP0_STATE_DATA_SEND,
    USB_DWC3_EP0_STATE_DATA_RECV,
    USB_DWC3_EP0_STATE_DATA_SEND_DONE,
    USB_DWC3_EP0_STATE_DATA_RECV_DONE,
    USB_DWC3_EP0_STATE_DATA_RECV_STATUS,
    USB_DWC3_EP0_STATE_DATA_RECV_STATUS_DONE,
    USB_DWC3_EP0_STATE_DATA_SEND_STATUS,
    USB_DWC3_EP0_STATE_DATA_SEND_STATUS_DONE
};

typedef struct dwc3_dev {
    /* USB DRD */
    uintptr_t regs;
    dart_dev_t *dart;

    enum ep0_state ep0_state;
    const void *ep0_buffer;
    u32 ep0_buffer_len;
    void *ep0_read_buffer;
    u32 ep0_read_buffer_len;

    void *evtbuffer;
    u32 evt_buffer_offset;

    void *scratchpad;
    void *xferbuffer;
    struct dwc3_trb *trbs;

    struct {
        bool xfer_in_progress;
        bool zlp_pending;

        void *xfer_buffer;
        uintptr_t xfer_buffer_iova;

        struct dwc3_trb *trb;
        uintptr_t trb_iova;
    } endpoints[MAX_ENDPOINTS];

    struct {
        ringbuffer_t *host2device;
        ringbuffer_t *device2host;
        u8 ep_intr;
        u8 ep_in;
        u8 ep_out;
        bool ready;
        /* USB ACM CDC serial */
        u8 cdc_line_coding[7];
    } pipe[CDC_ACM_PIPE_MAX];

} dwc3_dev_t;

static const struct usb_string_descriptor str_manufacturer =
    make_usb_string_descriptor("Asahi Linux");
static const struct usb_string_descriptor str_product =
    make_usb_string_descriptor("m1n1 uartproxy " BUILD_TAG);
static const struct usb_string_descriptor str_serial = make_usb_string_descriptor("P-0");

static const struct usb_string_descriptor_languages str_langs = {
    .bLength = sizeof(str_langs) + 2,
    .bDescriptorType = USB_STRING_DESCRIPTOR,
    .wLANGID = {USB_LANGID_EN_US},
};

struct cdc_dev_desc {
    const struct usb_configuration_descriptor configuration;
    const struct usb_interface_descriptor interface_management;
    const struct cdc_union_functional_descriptor cdc_union_func;
    const struct usb_endpoint_descriptor endpoint_notification;
    const struct usb_interface_descriptor interface_data;
    const struct usb_endpoint_descriptor endpoint_data_in;
    const struct usb_endpoint_descriptor endpoint_data_out;
    const struct usb_interface_descriptor sec_interface_management;
    const struct cdc_union_functional_descriptor sec_cdc_union_func;
    const struct usb_endpoint_descriptor sec_endpoint_notification;
    const struct usb_interface_descriptor sec_interface_data;
    const struct usb_endpoint_descriptor sec_endpoint_data_in;
    const struct usb_endpoint_descriptor sec_endpoint_data_out;
} PACKED;

static const struct usb_device_descriptor usb_cdc_device_descriptor = {
    .bLength = sizeof(struct usb_device_descriptor),
    .bDescriptorType = USB_DEVICE_DESCRIPTOR,
    .bcdUSB = 0x0200,
    .bDeviceClass = CDC_DEVICE_CLASS,
    .bDeviceSubClass = 0, // unused
    .bDeviceProtocol = 0, // unused
    .bMaxPacketSize0 = 64,
    .idVendor = CDC_USB_VID,
    .idProduct = CDC_USB_PID,
    .bcdDevice = 0x0100,
    .iManufacturer = STRING_DESCRIPTOR_MANUFACTURER,
    .iProduct = STRING_DESCRIPTOR_PRODUCT,
    .iSerialNumber = STRING_DESCRIPTOR_SERIAL,
    .bNumConfigurations = 1,
};

static const struct cdc_dev_desc cdc_configuration_descriptor = {
    .configuration =
        {
            .bLength = sizeof(cdc_configuration_descriptor.configuration),
            .bDescriptorType = USB_CONFIGURATION_DESCRIPTOR,
            .wTotalLength = sizeof(cdc_configuration_descriptor),
            .bNumInterfaces = 4,
            .bConfigurationValue = 1,
            .iConfiguration = 0,
            .bmAttributes = USB_CONFIGURATION_ATTRIBUTE_RES1 | USB_CONFIGURATION_SELF_POWERED,
            .bMaxPower = 250,

        },
    .interface_management =
        {
            .bLength = sizeof(cdc_configuration_descriptor.interface_management),
            .bDescriptorType = USB_INTERFACE_DESCRIPTOR,
            .bInterfaceNumber = 0,
            .bAlternateSetting = 0,
            .bNumEndpoints = 1,
            .bInterfaceClass = CDC_INTERFACE_CLASS,
            .bInterfaceSubClass = CDC_INTERFACE_SUBCLASS_ACM,
            .bInterfaceProtocol = CDC_INTERFACE_PROTOCOL_NONE,
            .iInterface = 0,

        },
    .cdc_union_func =
        {
            .bFunctionLength = sizeof(cdc_configuration_descriptor.cdc_union_func),
            .bDescriptorType = USB_CDC_INTERFACE_FUNCTIONAL_DESCRIPTOR,
            .bDescriptorSubtype = USB_CDC_UNION_SUBTYPE,
            .bControlInterface = 0,
            .bDataInterface = 1,
        },
    /*
     * we never use this endpoint, but it should exist and always be idle.
     * it needs to exist in the descriptor though to make hosts correctly recognize
     * us as a ACM CDC device.
     */
    .endpoint_notification =
        {
            .bLength = sizeof(cdc_configuration_descriptor.endpoint_notification),
            .bDescriptorType = USB_ENDPOINT_DESCRIPTOR,
            .bEndpointAddress = USB_ENDPOINT_ADDR_IN(1),
            .bmAttributes = USB_ENDPOINT_ATTR_TYPE_INTERRUPT,
            .wMaxPacketSize = 64,
            .bInterval = 10,

        },
    .interface_data =
        {
            .bLength = sizeof(cdc_configuration_descriptor.interface_data),
            .bDescriptorType = USB_INTERFACE_DESCRIPTOR,
            .bInterfaceNumber = 1,
            .bAlternateSetting = 0,
            .bNumEndpoints = 2,
            .bInterfaceClass = CDC_INTERFACE_CLASS_DATA,
            .bInterfaceSubClass = 0, // unused
            .bInterfaceProtocol = 0, // unused
            .iInterface = 0,
        },
    .endpoint_data_in =
        {
            .bLength = sizeof(cdc_configuration_descriptor.endpoint_data_in),
            .bDescriptorType = USB_ENDPOINT_DESCRIPTOR,
            .bEndpointAddress = USB_ENDPOINT_ADDR_OUT(2),
            .bmAttributes = USB_ENDPOINT_ATTR_TYPE_BULK,
            .wMaxPacketSize = 512,
            .bInterval = 10,
        },
    .endpoint_data_out =
        {
            .bLength = sizeof(cdc_configuration_descriptor.endpoint_data_out),
            .bDescriptorType = USB_ENDPOINT_DESCRIPTOR,
            .bEndpointAddress = USB_ENDPOINT_ADDR_IN(2),
            .bmAttributes = USB_ENDPOINT_ATTR_TYPE_BULK,
            .wMaxPacketSize = 512,
            .bInterval = 10,
        },

    /*
     * CDC ACM interface for virtual uart
     */

    .sec_interface_management =
        {
            .bLength = sizeof(cdc_configuration_descriptor.sec_interface_management),
            .bDescriptorType = USB_INTERFACE_DESCRIPTOR,
            .bInterfaceNumber = 2,
            .bAlternateSetting = 0,
            .bNumEndpoints = 1,
            .bInterfaceClass = CDC_INTERFACE_CLASS,
            .bInterfaceSubClass = CDC_INTERFACE_SUBCLASS_ACM,
            .bInterfaceProtocol = CDC_INTERFACE_PROTOCOL_NONE,
            .iInterface = 0,

        },
    .sec_cdc_union_func =
        {
            .bFunctionLength = sizeof(cdc_configuration_descriptor.sec_cdc_union_func),
            .bDescriptorType = USB_CDC_INTERFACE_FUNCTIONAL_DESCRIPTOR,
            .bDescriptorSubtype = USB_CDC_UNION_SUBTYPE,
            .bControlInterface = 2,
            .bDataInterface = 3,
        },
    /*
     * we never use this endpoint, but it should exist and always be idle.
     * it needs to exist in the descriptor though to make hosts correctly recognize
     * us as a ACM CDC device.
     */
    .sec_endpoint_notification =
        {
            .bLength = sizeof(cdc_configuration_descriptor.sec_endpoint_notification),
            .bDescriptorType = USB_ENDPOINT_DESCRIPTOR,
            .bEndpointAddress = USB_ENDPOINT_ADDR_IN(3),
            .bmAttributes = USB_ENDPOINT_ATTR_TYPE_INTERRUPT,
            .wMaxPacketSize = 64,
            .bInterval = 10,

        },
    .sec_interface_data =
        {
            .bLength = sizeof(cdc_configuration_descriptor.sec_interface_data),
            .bDescriptorType = USB_INTERFACE_DESCRIPTOR,
            .bInterfaceNumber = 3,
            .bAlternateSetting = 0,
            .bNumEndpoints = 2,
            .bInterfaceClass = CDC_INTERFACE_CLASS_DATA,
            .bInterfaceSubClass = 0, // unused
            .bInterfaceProtocol = 0, // unused
            .iInterface = 0,
        },
    .sec_endpoint_data_in =
        {
            .bLength = sizeof(cdc_configuration_descriptor.sec_endpoint_data_in),
            .bDescriptorType = USB_ENDPOINT_DESCRIPTOR,
            .bEndpointAddress = USB_ENDPOINT_ADDR_OUT(4),
            .bmAttributes = USB_ENDPOINT_ATTR_TYPE_BULK,
            .wMaxPacketSize = 512,
            .bInterval = 10,
        },
    .sec_endpoint_data_out =
        {
            .bLength = sizeof(cdc_configuration_descriptor.sec_endpoint_data_out),
            .bDescriptorType = USB_ENDPOINT_DESCRIPTOR,
            .bEndpointAddress = USB_ENDPOINT_ADDR_IN(4),
            .bmAttributes = USB_ENDPOINT_ATTR_TYPE_BULK,
            .wMaxPacketSize = 512,
            .bInterval = 10,
        },
};

static const struct usb_device_qualifier_descriptor usb_cdc_device_qualifier_descriptor = {
    .bLength = sizeof(struct usb_device_qualifier_descriptor),
    .bDescriptorType = USB_DEVICE_QUALIFIER_DESCRIPTOR,
    .bcdUSB = 0x0200,
    .bDeviceClass = CDC_DEVICE_CLASS,
    .bDeviceSubClass = 0, // unused
    .bDeviceProtocol = 0, // unused
    .bMaxPacketSize0 = 64,
    .bNumConfigurations = 0,
};

static const char *devt_names[] = {
    "DisconnEvt", "USBRst",   "ConnectDone", "ULStChng", "WkUpEvt",      "Reserved",       "EOPF",
    "SOF",        "Reserved", "ErrticErr",   "CmdCmplt", "EvntOverflow", "VndrDevTstRcved"};
static const char *depvt_names[] = {
    "Reserved",
    "XferComplete",
    "XferInProgress",
    "XferNotReady",
    "RxTxFifoEvt (IN->Underrun, OUT->Overrun)",
    "Reserved",
    "StreamEvt",
    "EPCmdCmplt",
};

static const char *ep0_state_names[] = {
    "STATE_IDLE",
    "STATE_SETUP_HANDLE",
    "STATE_DATA_SEND",
    "STATE_DATA_RECV",
    "STATE_DATA_SEND_DONE",
    "STATE_DATA_RECV_DONE",
    "STATE_DATA_RECV_STATUS",
    "STATE_DATA_RECV_STATUS_DONE",
    "STATE_DATA_SEND_STATUS",
    "STATE_DATA_SEND_STATUS_DONE",
};

static u8 ep_to_num(u8 epno)
{
    return (epno << 1) | (epno >> 7);
}

static int usb_dwc3_command(dwc3_dev_t *dev, u32 command, u32 par)
{
    write32(dev->regs + DWC3_DGCMDPAR, par);
    write32(dev->regs + DWC3_DGCMD, command | DWC3_DGCMD_CMDACT);

    if (poll32(dev->regs + DWC3_DGCMD, DWC3_DGCMD_CMDACT, 0, 1000)) {
        usb_debug_printf("timeout while waiting for DWC3_DGCMD_CMDACT to clear.\n");
        return -1;
    }

    return DWC3_DGCMD_STATUS(read32(dev->regs + DWC3_DGCMD));
}

static int usb_dwc3_ep_command(dwc3_dev_t *dev, u8 ep, u32 command, u32 par0, u32 par1, u32 par2)
{
    write32(dev->regs + DWC3_DEPCMDPAR0(ep), par0);
    write32(dev->regs + DWC3_DEPCMDPAR1(ep), par1);
    write32(dev->regs + DWC3_DEPCMDPAR2(ep), par2);
    write32(dev->regs + DWC3_DEPCMD(ep), command | DWC3_DEPCMD_CMDACT);

    if (poll32(dev->regs + DWC3_DEPCMD(ep), DWC3_DEPCMD_CMDACT, 0, 1000)) {
        usb_debug_printf("timeout while waiting for DWC3_DEPCMD_CMDACT to clear.\n");
        return -1;
    }

    return DWC3_DEPCMD_STATUS(read32(dev->regs + DWC3_DEPCMD(ep)));
}

static int usb_dwc3_ep_configure(dwc3_dev_t *dev, u8 ep, u8 type, u32 max_packet_len)
{
    u32 param0, param1;

    param0 = DWC3_DEPCFG_EP_TYPE(type) | DWC3_DEPCFG_MAX_PACKET_SIZE(max_packet_len);
    if (type != DWC3_DEPCMD_TYPE_CONTROL)
        param0 |= DWC3_DEPCFG_FIFO_NUMBER(ep);

    param1 =
        DWC3_DEPCFG_XFER_COMPLETE_EN | DWC3_DEPCFG_XFER_NOT_READY_EN | DWC3_DEPCFG_EP_NUMBER(ep);

    if (usb_dwc3_ep_command(dev, ep, DWC3_DEPCMD_SETEPCONFIG, param0, param1, 0)) {
        usb_debug_printf("cannot issue DWC3_DEPCMD_SETEPCONFIG for EP %d.\n", ep);
        return -1;
    }

    if (usb_dwc3_ep_command(dev, ep, DWC3_DEPCMD_SETTRANSFRESOURCE, 1, 0, 0)) {
        usb_debug_printf("cannot issue DWC3_DEPCMD_SETTRANSFRESOURCE EP %d.\n", ep);
        return -1;
    }

    return 0;
}

static int usb_dwc3_ep_start_transfer(dwc3_dev_t *dev, u8 ep, uintptr_t trb_iova)
{
    if (dev->endpoints[ep].xfer_in_progress) {
        usb_debug_printf(
            "Tried to start a transfer for ep 0x%02x while another transfer is ongoing.\n", ep);
        return -1;
    }

    dma_wmb();
    int ret =
        usb_dwc3_ep_command(dev, ep, DWC3_DEPCMD_STARTTRANSFER, trb_iova >> 32, (u32)trb_iova, 0);
    if (ret) {
        usb_debug_printf("cannot issue DWC3_DEPCMD_STARTTRANSFER for EP %d: %d.\n", ep, ret);
        return ret;
    }

    dev->endpoints[ep].xfer_in_progress = true;
    return 0;
}

static uintptr_t usb_dwc3_init_trb(dwc3_dev_t *dev, u8 ep, struct dwc3_trb **trb)
{
    struct dwc3_trb *next_trb = dev->endpoints[ep].trb;

    if (trb)
        *trb = next_trb;

    next_trb->ctrl = DWC3_TRB_CTRL_HWO | DWC3_TRB_CTRL_ISP_IMI | DWC3_TRB_CTRL_LST;
    next_trb->size = DWC3_TRB_SIZE_LENGTH(0);
    next_trb->bph = 0;
    next_trb->bpl = dev->endpoints[ep].xfer_buffer_iova;

    return dev->endpoints[ep].trb_iova;
}

static int usb_dwc3_run_data_trb(dwc3_dev_t *dev, u8 ep, u32 data_len)
{
    struct dwc3_trb *trb;
    uintptr_t trb_iova = usb_dwc3_init_trb(dev, ep, &trb);

    trb->ctrl |= DWC3_TRBCTL_CONTROL_DATA;
    trb->size = DWC3_TRB_SIZE_LENGTH(data_len);

    return usb_dwc3_ep_start_transfer(dev, ep, trb_iova);
}

static int usb_dwc3_start_setup_phase(dwc3_dev_t *dev)
{
    struct dwc3_trb *trb;
    uintptr_t trb_iova = usb_dwc3_init_trb(dev, USB_LEP_CTRL_OUT, &trb);

    trb->ctrl |= DWC3_TRBCTL_CONTROL_SETUP;
    trb->size = DWC3_TRB_SIZE_LENGTH(sizeof(union usb_setup_packet));
    return usb_dwc3_ep_start_transfer(dev, USB_LEP_CTRL_OUT, trb_iova);
}

static int usb_dwc3_start_status_phase(dwc3_dev_t *dev, u8 ep)
{
    struct dwc3_trb *trb;
    uintptr_t trb_iova = usb_dwc3_init_trb(dev, ep, &trb);

    trb->ctrl |= DWC3_TRBCTL_CONTROL_STATUS2;
    trb->size = DWC3_TRB_SIZE_LENGTH(0);

    return usb_dwc3_ep_start_transfer(dev, ep, trb_iova);
}

static int usb_dwc3_ep0_start_data_send_phase(dwc3_dev_t *dev)
{
    if (dev->ep0_buffer_len > XFER_BUFFER_BYTES_PER_EP) {
        usb_debug_printf("Cannot xfer more than %d bytes but was requested to xfer %d on ep 1\n",
                         XFER_BUFFER_BYTES_PER_EP, dev->ep0_buffer_len);
        return -1;
    }

    memset(dev->endpoints[USB_LEP_CTRL_IN].xfer_buffer, 0, 64);
    memcpy(dev->endpoints[USB_LEP_CTRL_IN].xfer_buffer, dev->ep0_buffer, dev->ep0_buffer_len);

    return usb_dwc3_run_data_trb(dev, USB_LEP_CTRL_IN, dev->ep0_buffer_len);
}

static int usb_dwc3_ep0_start_data_recv_phase(dwc3_dev_t *dev)
{
    if (dev->ep0_buffer_len > XFER_BUFFER_BYTES_PER_EP) {
        usb_debug_printf("Cannot xfer more than %d bytes but was requested to xfer %d on ep 0\n",
                         XFER_BUFFER_BYTES_PER_EP, dev->ep0_buffer_len);
        return -1;
    }

    memset(dev->endpoints[USB_LEP_CTRL_OUT].xfer_buffer, 0, 64);

    return usb_dwc3_run_data_trb(dev, USB_LEP_CTRL_OUT, 64);
}

static void usb_dwc3_ep_set_stall(dwc3_dev_t *dev, u8 ep, u8 stall)
{
    if (stall)
        usb_dwc3_ep_command(dev, ep, DWC3_DEPCMD_SETSTALL, 0, 0, 0);
    else
        usb_dwc3_ep_command(dev, ep, DWC3_DEPCMD_CLEARSTALL, 0, 0, 0);
}

static void usb_cdc_get_string_descriptor(u32 index, const void **descriptor, u16 *descriptor_len)
{
    switch (index) {
        case STRING_DESCRIPTOR_LANGUAGES:
            *descriptor = &str_langs;
            *descriptor_len = str_langs.bLength;
            break;
        case STRING_DESCRIPTOR_MANUFACTURER:
            *descriptor = &str_manufacturer;
            *descriptor_len = str_manufacturer.bLength;
            break;
        case STRING_DESCRIPTOR_PRODUCT:
            *descriptor = &str_product;
            *descriptor_len = str_product.bLength;
            break;
        case STRING_DESCRIPTOR_SERIAL:
            *descriptor = &str_serial;
            *descriptor_len = str_serial.bLength;
            break;
        default:
            *descriptor = NULL;
            *descriptor_len = 0;
    }
}

static int
usb_dwc3_handle_ep0_get_descriptor(dwc3_dev_t *dev,
                                   const struct usb_setup_packet_get_descriptor *get_descriptor)
{
    const void *descriptor = NULL;
    u16 descriptor_len = 0;

    switch (get_descriptor->type) {
        case USB_DEVICE_DESCRIPTOR:
            descriptor = &usb_cdc_device_descriptor;
            descriptor_len = usb_cdc_device_descriptor.bLength;
            break;
        case USB_CONFIGURATION_DESCRIPTOR:
            descriptor = &cdc_configuration_descriptor;
            descriptor_len = cdc_configuration_descriptor.configuration.wTotalLength;
            break;
        case USB_STRING_DESCRIPTOR:
            usb_cdc_get_string_descriptor(get_descriptor->index, &descriptor, &descriptor_len);
            break;
        case USB_DEVICE_QUALIFIER_DESCRIPTOR:
            descriptor = &usb_cdc_device_qualifier_descriptor;
            descriptor_len = usb_cdc_device_qualifier_descriptor.bLength;
            break;
        default:
            usb_debug_printf("Unknown descriptor type: %d\n", get_descriptor->type);
            break;
    }

    if (descriptor) {
        dev->ep0_buffer = descriptor;
        dev->ep0_buffer_len = min(get_descriptor->wLength, descriptor_len);
        return 0;
    } else {
        return -1;
    }
}

static void usb_dwc3_ep0_handle_standard_device(dwc3_dev_t *dev,
                                                const union usb_setup_packet *setup)
{
    switch (setup->raw.bRequest) {
        case USB_REQUEST_SET_ADDRESS:
            mask32(dev->regs + DWC3_DCFG, DWC3_DCFG_DEVADDR_MASK,
                   DWC3_DCFG_DEVADDR(setup->set_address.address));
            dev->ep0_state = USB_DWC3_EP0_STATE_DATA_SEND_STATUS;
            break;

        case USB_REQUEST_SET_CONFIGURATION:
            switch (setup->set_configuration.configuration) {
                case 0:
                    clear32(dev->regs + DWC3_DALEPENA, DWC3_DALEPENA_EP(USB_LEP_CDC_BULK_OUT));
                    clear32(dev->regs + DWC3_DALEPENA, DWC3_DALEPENA_EP(USB_LEP_CDC_BULK_IN));
                    clear32(dev->regs + DWC3_DALEPENA, DWC3_DALEPENA_EP(USB_LEP_CDC_INTR_IN));
                    clear32(dev->regs + DWC3_DALEPENA, DWC3_DALEPENA_EP(USB_LEP_CDC_BULK_OUT_2));
                    clear32(dev->regs + DWC3_DALEPENA, DWC3_DALEPENA_EP(USB_LEP_CDC_BULK_IN_2));
                    clear32(dev->regs + DWC3_DALEPENA, DWC3_DALEPENA_EP(USB_LEP_CDC_INTR_IN_2));
                    dev->ep0_state = USB_DWC3_EP0_STATE_DATA_SEND_STATUS;
                    for (int i = 0; i < CDC_ACM_PIPE_MAX; i++)
                        dev->pipe[i].ready = false;
                    break;
                case 1:
                    /* we've already configured these endpoints so that we just need to enable them
                     * here */
                    set32(dev->regs + DWC3_DALEPENA, DWC3_DALEPENA_EP(USB_LEP_CDC_BULK_OUT));
                    set32(dev->regs + DWC3_DALEPENA, DWC3_DALEPENA_EP(USB_LEP_CDC_BULK_IN));
                    set32(dev->regs + DWC3_DALEPENA, DWC3_DALEPENA_EP(USB_LEP_CDC_INTR_IN));
                    set32(dev->regs + DWC3_DALEPENA, DWC3_DALEPENA_EP(USB_LEP_CDC_BULK_OUT_2));
                    set32(dev->regs + DWC3_DALEPENA, DWC3_DALEPENA_EP(USB_LEP_CDC_BULK_IN_2));
                    set32(dev->regs + DWC3_DALEPENA, DWC3_DALEPENA_EP(USB_LEP_CDC_INTR_IN_2));
                    dev->ep0_state = USB_DWC3_EP0_STATE_DATA_SEND_STATUS;
                    break;
                default:
                    usb_dwc3_ep_set_stall(dev, 0, 1);
                    dev->ep0_state = USB_DWC3_EP0_STATE_IDLE;
                    break;
            }
            break;

        case USB_REQUEST_GET_DESCRIPTOR:
            if (usb_dwc3_handle_ep0_get_descriptor(dev, &setup->get_descriptor) < 0) {
                usb_dwc3_ep_set_stall(dev, 0, 1);
                dev->ep0_state = USB_DWC3_EP0_STATE_IDLE;
            } else {
                dev->ep0_state = USB_DWC3_EP0_STATE_DATA_SEND;
            }
            break;

        case USB_REQUEST_GET_STATUS: {
            static const u16 device_status = 0x0001; // self-powered
            dev->ep0_buffer = &device_status;
            dev->ep0_buffer_len = 2;
            dev->ep0_state = USB_DWC3_EP0_STATE_DATA_SEND;
            break;
        }

        default:
            usb_dwc3_ep_set_stall(dev, 0, 1);
            dev->ep0_state = USB_DWC3_EP0_STATE_IDLE;
            usb_debug_printf("unsupported SETUP packet\n");
    }
}

static void usb_dwc3_ep0_handle_standard_interface(dwc3_dev_t *dev,
                                                   const union usb_setup_packet *setup)
{
    switch (setup->raw.bRequest) {
        case USB_REQUEST_GET_STATUS: {
            static const u16 device_status = 0x0000; // reserved
            dev->ep0_buffer = &device_status;
            dev->ep0_buffer_len = 2;
            dev->ep0_state = USB_DWC3_EP0_STATE_DATA_SEND;
            break;
        }
        default:
            usb_dwc3_ep_set_stall(dev, 0, 1);
            dev->ep0_state = USB_DWC3_EP0_STATE_IDLE;
            usb_debug_printf("unsupported SETUP packet\n");
    }
}

static void usb_dwc3_ep0_handle_standard_endpoint(dwc3_dev_t *dev,
                                                  const union usb_setup_packet *setup)
{
    switch (setup->raw.bRequest) {
        case USB_REQUEST_GET_STATUS: {
            static const u16 device_status = 0x0000; // reserved
            dev->ep0_buffer = &device_status;
            dev->ep0_buffer_len = 2;
            dev->ep0_state = USB_DWC3_EP0_STATE_DATA_SEND;
            break;
        }
        case USB_REQUEST_CLEAR_FEATURE: {
            switch (setup->feature.wFeatureSelector) {
                case USB_FEATURE_ENDPOINT_HALT:
                    usb_debug_printf("Host cleared EP 0x%x stall\n", setup->feature.wEndpoint);
                    usb_dwc3_ep_set_stall(dev, ep_to_num(setup->feature.wEndpoint), 0);
                    usb_dwc3_start_status_phase(dev, USB_LEP_CTRL_IN);
                    dev->ep0_state = USB_DWC3_EP0_STATE_DATA_SEND_STATUS_DONE;
                    break;
                default:
                    usb_dwc3_ep_set_stall(dev, 0, 1);
                    dev->ep0_state = USB_DWC3_EP0_STATE_IDLE;
                    usb_debug_printf("unsupported CLEAR FEATURE: 0x%x\n",
                                     setup->feature.wFeatureSelector);
                    break;
            }
            break;
        }
        default:
            usb_dwc3_ep_set_stall(dev, 0, 1);
            dev->ep0_state = USB_DWC3_EP0_STATE_IDLE;
            usb_debug_printf("unsupported SETUP packet\n");
    }
}

static void usb_dwc3_ep0_handle_standard(dwc3_dev_t *dev, const union usb_setup_packet *setup)
{
    switch (setup->raw.bmRequestType & USB_REQUEST_TYPE_RECIPIENT_MASK) {
        case USB_REQUEST_TYPE_RECIPIENT_DEVICE:
            usb_dwc3_ep0_handle_standard_device(dev, setup);
            break;

        case USB_REQUEST_TYPE_RECIPIENT_INTERFACE:
            usb_dwc3_ep0_handle_standard_interface(dev, setup);
            break;

        case USB_REQUEST_TYPE_RECIPIENT_ENDPOINT:
            usb_dwc3_ep0_handle_standard_endpoint(dev, setup);
            break;

        default:
            usb_dwc3_ep_set_stall(dev, 0, 1);
            dev->ep0_state = USB_DWC3_EP0_STATE_IDLE;
            usb_debug_printf("unimplemented request recipient\n");
    }
}

static void usb_dwc3_ep0_handle_class(dwc3_dev_t *dev, const union usb_setup_packet *setup)
{
    int pipe = setup->raw.wIndex / 2;

    switch (setup->raw.bRequest) {
        case USB_REQUEST_CDC_GET_LINE_CODING:
            dev->ep0_buffer_len = min(setup->raw.wLength, sizeof(dev->pipe[pipe].cdc_line_coding));
            dev->ep0_buffer = dev->pipe[pipe].cdc_line_coding;
            dev->ep0_state = USB_DWC3_EP0_STATE_DATA_SEND;
            break;

        case USB_REQUEST_CDC_SET_CTRL_LINE_STATE:
            if (setup->raw.wValue & 1) { // DTR
                dev->pipe[pipe].ready = false;
                usb_debug_printf("ACM device opened\n");
                dev->pipe[pipe].ready = true;
            } else {
                dev->pipe[pipe].ready = false;
                usb_debug_printf("ACM device closed\n");
            }
            usb_dwc3_start_status_phase(dev, USB_LEP_CTRL_IN);
            dev->ep0_state = USB_DWC3_EP0_STATE_DATA_SEND_STATUS_DONE;
            break;

        case USB_REQUEST_CDC_SET_LINE_CODING:
            dev->ep0_read_buffer = dev->pipe[pipe].cdc_line_coding;
            dev->ep0_read_buffer_len =
                min(setup->raw.wLength, sizeof(dev->pipe[pipe].cdc_line_coding));
            dev->ep0_state = USB_DWC3_EP0_STATE_DATA_RECV;
            break;

        default:
            usb_dwc3_ep_set_stall(dev, 0, 1);
            dev->ep0_state = USB_DWC3_EP0_STATE_IDLE;
            usb_debug_printf("unsupported SETUP packet\n");
    }
}

static void usb_dwc3_ep0_handle_setup(dwc3_dev_t *dev)
{
    const union usb_setup_packet *setup = dev->endpoints[0].xfer_buffer;

    switch (setup->raw.bmRequestType & USB_REQUEST_TYPE_MASK) {
        case USB_REQUEST_TYPE_STANDARD:
            usb_dwc3_ep0_handle_standard(dev, setup);
            break;
        case USB_REQUEST_TYPE_CLASS:
            usb_dwc3_ep0_handle_class(dev, setup);
            break;
        default:
            usb_debug_printf("unsupported request type\n");
            usb_dwc3_ep_set_stall(dev, 0, 1);
            dev->ep0_state = USB_DWC3_EP0_STATE_IDLE;
    }
}

static void usb_dwc3_ep0_handle_xfer_done(dwc3_dev_t *dev, const struct dwc3_event_depevt event)
{
    switch (dev->ep0_state) {
        case USB_DWC3_EP0_STATE_SETUP_HANDLE:
            usb_dwc3_ep0_handle_setup(dev);
            break;

        case USB_DWC3_EP0_STATE_DATA_RECV_STATUS_DONE:
        case USB_DWC3_EP0_STATE_DATA_SEND_STATUS_DONE:
            usb_dwc3_start_setup_phase(dev);
            dev->ep0_state = USB_DWC3_EP0_STATE_SETUP_HANDLE;
            break;

        case USB_DWC3_EP0_STATE_DATA_SEND_DONE:
            dev->ep0_state = USB_DWC3_EP0_STATE_DATA_RECV_STATUS;
            break;

        case USB_DWC3_EP0_STATE_DATA_RECV_DONE:
            memcpy(dev->ep0_read_buffer, dev->endpoints[event.endpoint_number].xfer_buffer,
                   dev->ep0_read_buffer_len);
            dev->ep0_state = USB_DWC3_EP0_STATE_DATA_SEND_STATUS;
            break;

        case USB_DWC3_EP0_STATE_IDLE:
        default:
            usb_debug_printf("invalid state in usb_dwc3_ep0_handle_xfer_done: %d, %s\n",
                             dev->ep0_state, ep0_state_names[dev->ep0_state]);
            usb_dwc3_ep_set_stall(dev, 0, 1);
            dev->ep0_state = USB_DWC3_EP0_STATE_IDLE;
    }
}

static void usb_dwc3_ep0_handle_xfer_not_ready(dwc3_dev_t *dev,
                                               const struct dwc3_event_depevt event)
{
    switch (dev->ep0_state) {
        case USB_DWC3_EP0_STATE_IDLE:
            usb_dwc3_start_setup_phase(dev);
            dev->ep0_state = USB_DWC3_EP0_STATE_SETUP_HANDLE;
            break;

        case USB_DWC3_EP0_STATE_DATA_SEND:
            if (usb_dwc3_ep0_start_data_send_phase(dev))
                usb_debug_printf("cannot start xtrl xfer data phase for EP 1.\n");
            dev->ep0_state = USB_DWC3_EP0_STATE_DATA_SEND_DONE;
            break;

        case USB_DWC3_EP0_STATE_DATA_RECV:
            if (usb_dwc3_ep0_start_data_recv_phase(dev))
                usb_debug_printf("cannot start xtrl xfer data phase for EP 0.\n");
            dev->ep0_state = USB_DWC3_EP0_STATE_DATA_RECV_DONE;
            break;

        case USB_DWC3_EP0_STATE_DATA_RECV_STATUS:
            usb_dwc3_start_status_phase(dev, USB_LEP_CTRL_OUT);
            dev->ep0_state = USB_DWC3_EP0_STATE_DATA_RECV_STATUS_DONE;
            break;

        case USB_DWC3_EP0_STATE_DATA_SEND_STATUS:
            usb_dwc3_start_status_phase(dev, USB_LEP_CTRL_IN);
            dev->ep0_state = USB_DWC3_EP0_STATE_DATA_SEND_STATUS_DONE;
            break;

        default:
            usb_debug_printf(
                "invalid state in usb_dwc3_ep0_handle_xfer_not_ready: %d, %s for ep %d (%x)\n",
                dev->ep0_state, ep0_state_names[dev->ep0_state], event.endpoint_number,
                event.endpoint_event);
            usb_dwc3_ep_set_stall(dev, 0, 1);
            dev->ep0_state = USB_DWC3_EP0_STATE_IDLE;
    }
}

ringbuffer_t *usb_dwc3_cdc_get_ringbuffer(dwc3_dev_t *dev, u8 endpoint_number)
{
    switch (endpoint_number) {
        case USB_LEP_CDC_BULK_IN:
            return dev->pipe[CDC_ACM_PIPE_0].device2host;
        case USB_LEP_CDC_BULK_OUT:
            return dev->pipe[CDC_ACM_PIPE_0].host2device;
        case USB_LEP_CDC_BULK_IN_2:
            return dev->pipe[CDC_ACM_PIPE_1].device2host;
        case USB_LEP_CDC_BULK_OUT_2:
            return dev->pipe[CDC_ACM_PIPE_1].host2device;
        default:
            return NULL;
    }
}

static void usb_dwc3_cdc_start_bulk_out_xfer(dwc3_dev_t *dev, u8 endpoint_number)
{
    struct dwc3_trb *trb;
    uintptr_t trb_iova;

    if (dev->endpoints[endpoint_number].xfer_in_progress)
        return;

    ringbuffer_t *host2device = usb_dwc3_cdc_get_ringbuffer(dev, endpoint_number);
    if (!host2device)
        return;

    if (ringbuffer_get_free(host2device) < XFER_SIZE)
        return;

    memset(dev->endpoints[endpoint_number].xfer_buffer, 0xaa, XFER_SIZE);
    trb_iova = usb_dwc3_init_trb(dev, endpoint_number, &trb);
    trb->ctrl |= DWC3_TRBCTL_NORMAL;
    trb->size = DWC3_TRB_SIZE_LENGTH(XFER_SIZE);

    usb_dwc3_ep_start_transfer(dev, endpoint_number, trb_iova);
    dev->endpoints[endpoint_number].xfer_in_progress = true;
}

static void usb_dwc3_cdc_start_bulk_in_xfer(dwc3_dev_t *dev, u8 endpoint_number)
{
    struct dwc3_trb *trb;
    uintptr_t trb_iova;

    if (dev->endpoints[endpoint_number].xfer_in_progress)
        return;

    ringbuffer_t *device2host = usb_dwc3_cdc_get_ringbuffer(dev, endpoint_number);
    if (!device2host)
        return;

    size_t len =
        ringbuffer_read(dev->endpoints[endpoint_number].xfer_buffer, XFER_SIZE, device2host);

    if (!len && !dev->endpoints[endpoint_number].zlp_pending)
        return;

    trb_iova = usb_dwc3_init_trb(dev, endpoint_number, &trb);
    trb->ctrl |= DWC3_TRBCTL_NORMAL;
    trb->size = DWC3_TRB_SIZE_LENGTH(len);

    usb_dwc3_ep_start_transfer(dev, endpoint_number, trb_iova);
    dev->endpoints[endpoint_number].xfer_in_progress = true;
    dev->endpoints[endpoint_number].zlp_pending = (len % 512) == 0;
}

static void usb_dwc3_cdc_handle_bulk_out_xfer_done(dwc3_dev_t *dev,
                                                   const struct dwc3_event_depevt event)
{
    ringbuffer_t *host2device = usb_dwc3_cdc_get_ringbuffer(dev, event.endpoint_number);
    if (!host2device)
        return;
    size_t len = min(XFER_SIZE, ringbuffer_get_free(host2device));
    ringbuffer_write(dev->endpoints[event.endpoint_number].xfer_buffer,
                     len - dev->endpoints[event.endpoint_number].trb->size, host2device);
}

static void usb_dwc3_handle_event_ep(dwc3_dev_t *dev, const struct dwc3_event_depevt event)
{
    if (event.endpoint_event == DWC3_DEPEVT_XFERCOMPLETE) {
        dev->endpoints[event.endpoint_number].xfer_in_progress = false;

        switch (event.endpoint_number) {
            case USB_LEP_CTRL_IN:
            case USB_LEP_CTRL_OUT:
                return usb_dwc3_ep0_handle_xfer_done(dev, event);
            case USB_LEP_CDC_INTR_IN: // [[fallthrough]]
            case USB_LEP_CDC_INTR_IN_2:
                return;
            case USB_LEP_CDC_BULK_IN: // [[fallthrough]]
            case USB_LEP_CDC_BULK_IN_2:
                return;
            case USB_LEP_CDC_BULK_OUT: // [[fallthrough]]
            case USB_LEP_CDC_BULK_OUT_2:
                return usb_dwc3_cdc_handle_bulk_out_xfer_done(dev, event);
        }
    } else if (event.endpoint_event == DWC3_DEPEVT_XFERNOTREADY) {
        /*
         * this might be a bug, we sometimes get spurious events like these here.
         * ignoring them works just fine though
         */
        if (dev->endpoints[event.endpoint_number].xfer_in_progress)
            return;

        switch (event.endpoint_number) {
            case USB_LEP_CTRL_IN:
            case USB_LEP_CTRL_OUT:
                return usb_dwc3_ep0_handle_xfer_not_ready(dev, event);
            case USB_LEP_CDC_INTR_IN: // [[fallthrough]]
            case USB_LEP_CDC_INTR_IN_2:
                return;
            case USB_LEP_CDC_BULK_IN: // [[fallthrough]]
            case USB_LEP_CDC_BULK_IN_2:
                return usb_dwc3_cdc_start_bulk_in_xfer(dev, event.endpoint_number);
            case USB_LEP_CDC_BULK_OUT: // [[fallthrough]]
            case USB_LEP_CDC_BULK_OUT_2:
                return usb_dwc3_cdc_start_bulk_out_xfer(dev, event.endpoint_number);
        }
    }

    usb_debug_printf("unhandled EP %02x event: %s (0x%02x) (%d)\n", event.endpoint_number,
                     depvt_names[event.endpoint_event], event.endpoint_event,
                     dev->endpoints[event.endpoint_number].xfer_in_progress);
    usb_dwc3_ep_set_stall(dev, event.endpoint_event, 1);
}

static void usb_dwc3_handle_event_usbrst(dwc3_dev_t *dev)
{
    /* clear STALL mode for all endpoints */
    dev->endpoints[0].xfer_in_progress = false;
    for (int i = 1; i < MAX_ENDPOINTS; ++i) {
        dev->endpoints[i].xfer_in_progress = false;
        memset(dev->endpoints[i].xfer_buffer, 0, XFER_BUFFER_BYTES_PER_EP);
        memset(dev->endpoints[i].trb, 0, TRBS_PER_EP * sizeof(struct dwc3_trb));
        usb_dwc3_ep_set_stall(dev, i, 0);
    }

    /* set device address back to zero */
    mask32(dev->regs + DWC3_DCFG, DWC3_DCFG_DEVADDR_MASK, DWC3_DCFG_DEVADDR(0));

    /* only keep control endpoints enabled */
    write32(dev->regs + DWC3_DALEPENA, DWC3_DALEPENA_EP(0) | DWC3_DALEPENA_EP(1));
}

static void usb_dwc3_handle_event_connect_done(dwc3_dev_t *dev)
{
    u32 speed = read32(dev->regs + DWC3_DSTS) & DWC3_DSTS_CONNECTSPD;

    if (speed != DWC3_DSTS_HIGHSPEED) {
        usb_debug_printf(
            "WARNING: we only support high speed right now but %02x was requested in DSTS\n",
            speed);
    }

    usb_dwc3_start_setup_phase(dev);
    dev->ep0_state = USB_DWC3_EP0_STATE_SETUP_HANDLE;
}

static void usb_dwc3_handle_event_dev(dwc3_dev_t *dev, const struct dwc3_event_devt event)
{
    usb_debug_printf("device event: %s (0x%02x)\n", devt_names[event.type], event.type);
    switch (event.type) {
        case DWC3_DEVT_USBRST:
            usb_dwc3_handle_event_usbrst(dev);
            break;
        case DWC3_DEVT_CONNECTDONE:
            usb_dwc3_handle_event_connect_done(dev);
            break;
        default:
            usb_debug_printf("unhandled device event: %s (0x%02x)\n", devt_names[event.type],
                             event.type);
    }
}

static void usb_dwc3_handle_event(dwc3_dev_t *dev, const union dwc3_event event)
{
    if (!event.type.is_devspec)
        usb_dwc3_handle_event_ep(dev, event.depevt);
    else if (event.type.type == DWC3_EVENT_TYPE_DEV)
        usb_dwc3_handle_event_dev(dev, event.devt);
    else
        usb_debug_printf("unknown event %08x\n", event.raw);
}

void usb_dwc3_handle_events(dwc3_dev_t *dev)
{
    if (!dev)
        return;

    u32 n_events = read32(dev->regs + DWC3_GEVNTCOUNT(0)) / sizeof(union dwc3_event);
    if (n_events == 0)
        return;

    dma_rmb();

    const union dwc3_event *evtbuffer = dev->evtbuffer;
    for (u32 i = 0; i < n_events; ++i) {
        usb_dwc3_handle_event(dev, evtbuffer[dev->evt_buffer_offset]);

        dev->evt_buffer_offset =
            (dev->evt_buffer_offset + 1) % (DWC3_EVENT_BUFFERS_SIZE / sizeof(union dwc3_event));
    }

    write32(dev->regs + DWC3_GEVNTCOUNT(0), sizeof(union dwc3_event) * n_events);
}

dwc3_dev_t *usb_dwc3_init(uintptr_t regs, dart_dev_t *dart)
{
    /* sanity check */
    u32 snpsid = read32(regs + DWC3_GSNPSID);
    if ((snpsid & DWC3_GSNPSID_MASK) != 0x33310000) {
        debug_printf("no DWC3 core found at 0x%lx: %08x\n", regs, snpsid);
        return NULL;
    }

    dwc3_dev_t *dev = malloc(sizeof(*dev));
    if (!dev)
        return NULL;

    memset(dev, 0, sizeof(*dev));
    for (int i = 0; i < CDC_ACM_PIPE_MAX; i++)
        memcpy(dev->pipe[i].cdc_line_coding, cdc_default_line_coding,
               sizeof(cdc_default_line_coding));

    dev->regs = regs;
    dev->dart = dart;

    /* allocate and map dma buffers */
    dev->evtbuffer = memalign(SZ_16K, max(DWC3_EVENT_BUFFERS_SIZE, SZ_16K));
    if (!dev->evtbuffer)
        goto error;

    dev->scratchpad = memalign(SZ_16K, max(DWC3_SCRATCHPAD_SIZE, SZ_16K));
    if (!dev->scratchpad)
        goto error;

    dev->trbs = memalign(SZ_16K, TRB_BUFFER_SIZE);
    if (!dev->trbs)
        goto error;

    dev->xferbuffer = memalign(SZ_16K, XFER_BUFFER_SIZE);
    if (!dev->xferbuffer)
        goto error;

    memset(dev->evtbuffer, 0xaa, max(DWC3_EVENT_BUFFERS_SIZE, SZ_16K));
    memset(dev->scratchpad, 0, max(DWC3_SCRATCHPAD_SIZE, SZ_16K));
    memset(dev->xferbuffer, 0, XFER_BUFFER_SIZE);
    memset(dev->trbs, 0, TRB_BUFFER_SIZE);

    if (dart_map(dev->dart, EVENT_BUFFER_IOVA, dev->evtbuffer,
                 max(DWC3_EVENT_BUFFERS_SIZE, SZ_16K)))
        goto error;
    if (dart_map(dev->dart, SCRATCHPAD_IOVA, dev->scratchpad, max(DWC3_SCRATCHPAD_SIZE, SZ_16K)))
        goto error;
    if (dart_map(dev->dart, TRB_BUFFER_IOVA, dev->trbs, TRB_BUFFER_SIZE))
        goto error;
    if (dart_map(dev->dart, XFER_BUFFER_IOVA, dev->xferbuffer, XFER_BUFFER_SIZE))
        goto error;

    /* prepare endpoint buffers */
    for (int i = 0; i < MAX_ENDPOINTS; ++i) {
        u32 xferbuffer_offset = i * XFER_BUFFER_BYTES_PER_EP;
        dev->endpoints[i].xfer_buffer = dev->xferbuffer + xferbuffer_offset;
        dev->endpoints[i].xfer_buffer_iova = XFER_BUFFER_IOVA + xferbuffer_offset;

        u32 trb_offset = i * TRBS_PER_EP;
        dev->endpoints[i].trb = &dev->trbs[i * TRBS_PER_EP];
        dev->endpoints[i].trb_iova = TRB_BUFFER_IOVA + trb_offset * sizeof(struct dwc3_trb);
    }

    /* reset the device side of the controller */
    set32(dev->regs + DWC3_DCTL, DWC3_DCTL_CSFTRST);
    if (poll32(dev->regs + DWC3_DCTL, DWC3_DCTL_CSFTRST, 0, 1000)) {
        usb_debug_printf("timeout while waiting for DWC3_DCTL_CSFTRST to clear.\n");
        goto error;
    }

    /* soft reset the core and phy */
    set32(dev->regs + DWC3_GCTL, DWC3_GCTL_CORESOFTRESET);
    set32(dev->regs + DWC3_GUSB3PIPECTL(0), DWC3_GUSB3PIPECTL_PHYSOFTRST);
    set32(dev->regs + DWC3_GUSB2PHYCFG(0), DWC3_GUSB2PHYCFG_PHYSOFTRST);
    mdelay(100);
    clear32(dev->regs + DWC3_GUSB3PIPECTL(0), DWC3_GUSB3PIPECTL_PHYSOFTRST);
    clear32(dev->regs + DWC3_GUSB2PHYCFG(0), DWC3_GUSB2PHYCFG_PHYSOFTRST);
    mdelay(100);
    clear32(dev->regs + DWC3_GCTL, DWC3_GCTL_CORESOFTRESET);
    mdelay(100);

    /* disable unused features */
    clear32(dev->regs + DWC3_GCTL, DWC3_GCTL_SCALEDOWN_MASK | DWC3_GCTL_DISSCRAMBLE);

    /* switch to device-only mode */
    mask32(dev->regs + DWC3_GCTL, DWC3_GCTL_PRTCAPDIR(DWC3_GCTL_PRTCAP_OTG),
           DWC3_GCTL_PRTCAPDIR(DWC3_GCTL_PRTCAP_DEVICE));

    /* stick to USB 2.0 high speed for now */
    mask32(dev->regs + DWC3_DCFG, DWC3_DCFG_SPEED_MASK, DWC3_DCFG_HIGHSPEED);

    /* setup scratchpad at SCRATCHPAD_IOVA */
    if (usb_dwc3_command(dev, DWC3_DGCMD_SET_SCRATCHPAD_ADDR_LO, SCRATCHPAD_IOVA)) {
        usb_debug_printf("DWC3_DGCMD_SET_SCRATCHPAD_ADDR_LO failed.");
        goto error;
    }
    if (usb_dwc3_command(dev, DWC3_DGCMD_SET_SCRATCHPAD_ADDR_HI, 0)) {
        usb_debug_printf("DWC3_DGCMD_SET_SCRATCHPAD_ADDR_HI failed.");
        goto error;
    }

    /* setup a single event buffer at EVENT_BUFFER_IOVA */
    write32(dev->regs + DWC3_GEVNTADRLO(0), EVENT_BUFFER_IOVA);
    write32(dev->regs + DWC3_GEVNTADRHI(0), 0);
    write32(dev->regs + DWC3_GEVNTSIZ(0), DWC3_EVENT_BUFFERS_SIZE);
    write32(dev->regs + DWC3_GEVNTCOUNT(0), 0);

    /* enable connect, disconnect and reset events */
    write32(dev->regs + DWC3_DEVTEN,
            DWC3_DEVTEN_DISCONNEVTEN | DWC3_DEVTEN_USBRSTEN | DWC3_DEVTEN_CONNECTDONEEN);

    if (usb_dwc3_ep_command(dev, 0, DWC3_DEPCMD_DEPSTARTCFG, 0, 0, 0)) {
        usb_debug_printf("cannot issue initial DWC3_DEPCMD_DEPSTARTCFG.\n");
        goto error;
    }

    /* prepare control endpoint 0 IN and OUT */
    if (usb_dwc3_ep_configure(dev, USB_LEP_CTRL_OUT, DWC3_DEPCMD_TYPE_CONTROL, 64))
        goto error;
    if (usb_dwc3_ep_configure(dev, USB_LEP_CTRL_IN, DWC3_DEPCMD_TYPE_CONTROL, 64))
        goto error;

    /* prepare CDC ACM interfaces */

    dev->pipe[CDC_ACM_PIPE_0].ep_intr = USB_LEP_CDC_INTR_IN;
    dev->pipe[CDC_ACM_PIPE_0].ep_in = USB_LEP_CDC_BULK_IN;
    dev->pipe[CDC_ACM_PIPE_0].ep_out = USB_LEP_CDC_BULK_OUT;

    dev->pipe[CDC_ACM_PIPE_1].ep_intr = USB_LEP_CDC_INTR_IN_2;
    dev->pipe[CDC_ACM_PIPE_1].ep_in = USB_LEP_CDC_BULK_IN_2;
    dev->pipe[CDC_ACM_PIPE_1].ep_out = USB_LEP_CDC_BULK_OUT_2;

    for (int i = 0; i < CDC_ACM_PIPE_MAX; i++) {
        dev->pipe[i].host2device = ringbuffer_alloc(CDC_BUFFER_SIZE);
        if (!dev->pipe[i].host2device)
            goto error;
        dev->pipe[i].device2host = ringbuffer_alloc(CDC_BUFFER_SIZE);
        if (!dev->pipe[i].device2host)
            goto error;

        /* prepare INTR endpoint so that we don't have to reconfigure this device later */
        if (usb_dwc3_ep_configure(dev, dev->pipe[i].ep_intr, DWC3_DEPCMD_TYPE_INTR, 64))
            goto error;

        /* prepare BULK endpoints so that we don't have to reconfigure this device later */
        if (usb_dwc3_ep_configure(dev, dev->pipe[i].ep_in, DWC3_DEPCMD_TYPE_BULK, 512))
            goto error;
        if (usb_dwc3_ep_configure(dev, dev->pipe[i].ep_out, DWC3_DEPCMD_TYPE_BULK, 512))
            goto error;
    }

    /* prepare first control transfer */
    dev->ep0_state = USB_DWC3_EP0_STATE_IDLE;

    /* only enable control endpoints for now */
    write32(dev->regs + DWC3_DALEPENA,
            DWC3_DALEPENA_EP(USB_LEP_CTRL_IN) | DWC3_DALEPENA_EP(USB_LEP_CTRL_OUT));

    /* and finally kick the device controller to go live! */
    set32(dev->regs + DWC3_DCTL, DWC3_DCTL_RUN_STOP);

    return dev;

error:
    usb_dwc3_shutdown(dev);
    return NULL;
}

void usb_dwc3_shutdown(dwc3_dev_t *dev)
{
    for (int i = 0; i < CDC_ACM_PIPE_MAX; i++)
        dev->pipe[i].ready = false;

    /* stop all ongoing transfers */
    for (int i = 1; i < MAX_ENDPOINTS; ++i) {
        if (!dev->endpoints[i].xfer_in_progress)
            continue;

        if (usb_dwc3_ep_command(dev, i, DWC3_DEPCMD_ENDTRANSFER, 0, 0, 0))
            usb_debug_printf("cannot issue DWC3_DEPCMD_ENDTRANSFER for EP %02x.\n", i);
    }

    /* disable events and all endpoints and stop the device controller */
    write32(dev->regs + DWC3_DEVTEN, 0);
    write32(dev->regs + DWC3_DALEPENA, 0);
    clear32(dev->regs + DWC3_DCTL, DWC3_DCTL_RUN_STOP);

    /* wait until the controller is shut down */
    if (poll32(dev->regs + DWC3_DSTS, DWC3_DSTS_DEVCTRLHLT, DWC3_DSTS_DEVCTRLHLT, 1000))
        usb_debug_printf("timeout while waiting for DWC3_DSTS_DEVCTRLHLT during shutdown.\n");

    /* reset the device side of the controller just to be safe */
    set32(dev->regs + DWC3_DCTL, DWC3_DCTL_CSFTRST);
    if (poll32(dev->regs + DWC3_DCTL, DWC3_DCTL_CSFTRST, 0, 1000))
        usb_debug_printf("timeout while waiting for DWC3_DCTL_CSFTRST to clear during shutdown.\n");

    /* unmap and free dma buffers */
    dart_unmap(dev->dart, TRB_BUFFER_IOVA, TRB_BUFFER_SIZE);
    dart_unmap(dev->dart, XFER_BUFFER_IOVA, XFER_BUFFER_SIZE);
    dart_unmap(dev->dart, SCRATCHPAD_IOVA, max(DWC3_SCRATCHPAD_SIZE, SZ_16K));
    dart_unmap(dev->dart, EVENT_BUFFER_IOVA, max(DWC3_EVENT_BUFFERS_SIZE, SZ_16K));

    free(dev->evtbuffer);
    free(dev->scratchpad);
    free(dev->xferbuffer);
    free(dev->trbs);
    for (int i = 0; i < CDC_ACM_PIPE_MAX; i++) {
        ringbuffer_free(dev->pipe[i].device2host);
        ringbuffer_free(dev->pipe[i].host2device);
    }

    if (dev->dart)
        dart_shutdown(dev->dart);
    free(dev);
}

u8 usb_dwc3_getbyte(dwc3_dev_t *dev, cdc_acm_pipe_id_t pipe)
{
    ringbuffer_t *host2device = dev->pipe[pipe].host2device;
    if (!host2device)
        return 0;

    u8 ep = dev->pipe[pipe].ep_out;

    u8 c;
    while (ringbuffer_read(&c, 1, host2device) < 1) {
        usb_dwc3_handle_events(dev);
        usb_dwc3_cdc_start_bulk_out_xfer(dev, ep);
    }
    return c;
}

void usb_dwc3_putbyte(dwc3_dev_t *dev, cdc_acm_pipe_id_t pipe, u8 byte)
{
    ringbuffer_t *device2host = dev->pipe[pipe].device2host;
    if (!device2host)
        return;

    u8 ep = dev->pipe[pipe].ep_in;

    while (ringbuffer_write(&byte, 1, device2host) < 1) {
        usb_dwc3_handle_events(dev);
        usb_dwc3_cdc_start_bulk_in_xfer(dev, ep);
    }
}

size_t usb_dwc3_queue(dwc3_dev_t *dev, cdc_acm_pipe_id_t pipe, const void *buf, size_t count)
{
    const u8 *p = buf;
    size_t wrote, sent = 0;

    if (!dev || !dev->pipe[pipe].ready)
        return 0;

    ringbuffer_t *device2host = dev->pipe[pipe].device2host;
    if (!device2host)
        return 0;

    u8 ep = dev->pipe[pipe].ep_in;

    while (count) {
        wrote = ringbuffer_write(p, count, device2host);
        count -= wrote;
        p += wrote;
        sent += wrote;
        if (count) {
            usb_dwc3_handle_events(dev);
            usb_dwc3_cdc_start_bulk_in_xfer(dev, ep);
        }
    }

    return sent;
}

size_t usb_dwc3_write(dwc3_dev_t *dev, cdc_acm_pipe_id_t pipe, const void *buf, size_t count)
{
    if (!dev)
        return -1;

    u8 ep = dev->pipe[pipe].ep_in;
    size_t ret = usb_dwc3_queue(dev, pipe, buf, count);

    usb_dwc3_cdc_start_bulk_in_xfer(dev, ep);

    return ret;
}

size_t usb_dwc3_read(dwc3_dev_t *dev, cdc_acm_pipe_id_t pipe, void *buf, size_t count)
{
    u8 *p = buf;
    size_t read, recvd = 0;

    if (!dev || !dev->pipe[pipe].ready)
        return 0;

    ringbuffer_t *host2device = dev->pipe[pipe].host2device;
    if (!host2device)
        return 0;

    u8 ep = dev->pipe[pipe].ep_out;

    while (count) {
        read = ringbuffer_read(p, count, host2device);
        count -= read;
        p += read;
        recvd += read;
        usb_dwc3_handle_events(dev);
        usb_dwc3_cdc_start_bulk_out_xfer(dev, ep);
    }

    return recvd;
}

ssize_t usb_dwc3_can_read(dwc3_dev_t *dev, cdc_acm_pipe_id_t pipe)
{
    if (!dev || !dev->pipe[pipe].ready)
        return 0;

    ringbuffer_t *host2device = dev->pipe[pipe].host2device;
    if (!host2device)
        return 0;

    return ringbuffer_get_used(host2device);
}

bool usb_dwc3_can_write(dwc3_dev_t *dev, cdc_acm_pipe_id_t pipe)
{
    (void)pipe;
    if (!dev)
        return false;

    return dev->pipe[pipe].ready;
}

void usb_dwc3_flush(dwc3_dev_t *dev, cdc_acm_pipe_id_t pipe)
{
    if (!dev || !dev->pipe[pipe].ready)
        return;

    ringbuffer_t *device2host = dev->pipe[pipe].device2host;
    if (!device2host)
        return;

    u8 ep = dev->pipe[pipe].ep_in;

    while (ringbuffer_get_used(device2host) != 0 || dev->endpoints[ep].xfer_in_progress) {
        usb_dwc3_handle_events(dev);
    }
}
