/* SPDX-License-Identifier: MIT */

#ifndef USB_TYPES_H
#define USB_TYPES_H

#include "types.h"

#define USB_REQUEST_TYPE_DIRECTION_SHIFT       7
#define USB_REQUEST_TYPE_DIRECTION(d)          ((d) << USB_REQUEST_TYPE_DIRECTION_SHIFT)
#define USB_REQUEST_TYPE_DIRECTION_HOST2DEVICE 0
#define USB_REQUEST_TYPE_DIRECTION_DEVICE2HOST 1

#define USB_REQUEST_TYPE_SHIFT    5
#define USB_REQUEST_TYPE(t)       ((t) << USB_REQUEST_TYPE_SHIFT)
#define USB_REQUEST_TYPE_STANDARD USB_REQUEST_TYPE(0b00)
#define USB_REQUEST_TYPE_CLASS    USB_REQUEST_TYPE(0b01)
#define USB_REQUEST_TYPE_VENDOR   USB_REQUEST_TYPE(0b10)
#define USB_REQUEST_TYPE_MASK     USB_REQUEST_TYPE(0b11)

#define USB_REQUEST_TYPE_RECIPIENT_DEVICE    0
#define USB_REQUEST_TYPE_RECIPIENT_INTERFACE 1
#define USB_REQUEST_TYPE_RECIPIENT_ENDPOINT  2
#define USB_REQUEST_TYPE_RECIPIENT_OTHER     3
#define USB_REQUEST_TYPE_RECIPIENT_MASK      0b11

#define USB_REQUEST_GET_STATUS        0x00
#define USB_REQUEST_CLEAR_FEATURE     0x01
#define USB_REQUEST_SET_FEATURE       0x03
#define USB_REQUEST_SET_ADDRESS       0x05
#define USB_REQUEST_GET_DESCRIPTOR    0x06
#define USB_REQUEST_SET_DESCRIPTOR    0x07
#define USB_REQUEST_GET_CONFIGURATION 0x08
#define USB_REQUEST_SET_CONFIGURATION 0x09

#define USB_EP_REQUEST_CLEAR_FEATURE 0x01
#define USB_EP_REQUEST_SET_FEATURE   0x03

#define USB_FEATURE_ENDPOINT_HALT 0x00

#define USB_REQUEST_CDC_SET_LINE_CODING     0x20
#define USB_REQUEST_CDC_GET_LINE_CODING     0x21
#define USB_REQUEST_CDC_SET_CTRL_LINE_STATE 0x22

struct usb_setup_packet_raw {
    u8 bmRequestType;
    u8 bRequest;
    u16 wValue;
    u16 wIndex;
    u16 wLength;
} PACKED;

struct usb_setup_packet_get_descriptor {
    u8 bmRequestType;
    u8 bRequest;
    u8 index;
    u8 type;
    u16 language;
    u16 wLength;
} PACKED;

struct usb_set_packet_set_address {
    u8 bmRequestType;
    u8 bRequest;
    u16 address;
    u16 zero0;
    u16 zero1;
} PACKED;

struct usb_set_packet_set_configuration {
    u8 bmRequestType;
    u8 bRequest;
    u16 configuration;
    u16 zero0;
    u16 zero1;
} PACKED;

struct usb_setup_packet_feature {
    u8 bmRequestType;
    u8 bRequest;
    u16 wFeatureSelector;
    u16 wEndpoint;
    u16 wLength;
} PACKED;

union usb_setup_packet {
    struct usb_setup_packet_raw raw;
    struct usb_setup_packet_get_descriptor get_descriptor;
    struct usb_set_packet_set_address set_address;
    struct usb_set_packet_set_configuration set_configuration;
    struct usb_setup_packet_feature feature;
};

#define USB_DEVICE_DESCRIPTOR                    0x01
#define USB_CONFIGURATION_DESCRIPTOR             0x02
#define USB_STRING_DESCRIPTOR                    0x03
#define USB_INTERFACE_DESCRIPTOR                 0x04
#define USB_ENDPOINT_DESCRIPTOR                  0x05
#define USB_DEVICE_QUALIFIER_DESCRIPTOR          0x06
#define USB_OTHER_SPEED_CONFIGURATION_DESCRIPTOR 0x07

#define USB_CDC_INTERFACE_FUNCTIONAL_DESCRIPTOR 0x24
#define USB_CDC_UNION_SUBTYPE                   0x06

#define USB_CONFIGURATION_SELF_POWERED   0x40
#define USB_CONFIGURATION_ATTRIBUTE_RES1 0x80

#define USB_ENDPOINT_ADDR_IN(ep)  (0x80 | (ep))
#define USB_ENDPOINT_ADDR_OUT(ep) (0x00 | (ep))

#define USB_ENDPOINT_ATTR_TYPE_CONTROL     0b00
#define USB_ENDPOINT_ATTR_TYPE_ISOCHRONOUS 0b01
#define USB_ENDPOINT_ATTR_TYPE_BULK        0b10
#define USB_ENDPOINT_ATTR_TYPE_INTERRUPT   0b11

#define USB_LANGID_EN_US 0x0409

struct usb_device_descriptor {
    u8 bLength;
    u8 bDescriptorType;
    u16 bcdUSB;
    u8 bDeviceClass;
    u8 bDeviceSubClass;
    u8 bDeviceProtocol;
    u8 bMaxPacketSize0;
    u16 idVendor;
    u16 idProduct;
    u16 bcdDevice;
    u8 iManufacturer;
    u8 iProduct;
    u8 iSerialNumber;
    u8 bNumConfigurations;
} PACKED;

struct usb_configuration_descriptor {
    u8 bLength;
    u8 bDescriptorType;
    u16 wTotalLength;
    u8 bNumInterfaces;
    u8 bConfigurationValue;
    u8 iConfiguration;
    u8 bmAttributes;
    u8 bMaxPower;
} PACKED;

struct usb_interface_descriptor {
    u8 bLength;
    u8 bDescriptorType;
    u8 bInterfaceNumber;
    u8 bAlternateSetting;
    u8 bNumEndpoints;
    u8 bInterfaceClass;
    u8 bInterfaceSubClass;
    u8 bInterfaceProtocol;
    u8 iInterface;
} PACKED;

struct usb_endpoint_descriptor {
    u8 bLength;
    u8 bDescriptorType;
    u8 bEndpointAddress;
    u8 bmAttributes;
    u16 wMaxPacketSize;
    u8 bInterval;
} PACKED;

struct usb_string_descriptor {
    u8 bLength;
    u8 bDescriptorType;
    u16 bString[];
} PACKED;

struct usb_string_descriptor_languages {
    u8 bLength;
    u8 bDescriptorType;
    u16 wLANGID[];
} PACKED;

struct cdc_union_functional_descriptor {
    u8 bFunctionLength;
    u8 bDescriptorType;
    u8 bDescriptorSubtype;
    u8 bControlInterface;
    u8 bDataInterface;
} PACKED;

struct usb_device_qualifier_descriptor {
    u8 bLength;
    u8 bDescriptorType;
    u16 bcdUSB;
    u8 bDeviceClass;
    u8 bDeviceSubClass;
    u8 bDeviceProtocol;
    u8 bMaxPacketSize0;
    u8 bNumConfigurations;
    u8 bReserved;
} PACKED;

/*
 * this macro is required because we need to convert any string literals
 * to UTF16 and because we need to calculate the correct total size of the
 * string descriptor.
 */
#define make_usb_string_descriptor(str)                                                            \
    {                                                                                              \
        .bLength = sizeof(struct usb_string_descriptor) + sizeof(u##str),                          \
        .bDescriptorType = USB_STRING_DESCRIPTOR, .bString = u##str                                \
    }

#endif
