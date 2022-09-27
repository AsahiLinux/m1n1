# SPDX-License-Identifier: MIT

import struct
from io import BytesIO

from enum import IntEnum

from m1n1.proxyutils import RegMonitor
from m1n1.utils import *
from m1n1.trace.dart import DARTTracer
from m1n1.trace.asc import ASCTracer, EP, EPState, msg, msg_log, DIR
from m1n1.fw.afk.rbep import *
from m1n1.fw.afk.epic import *

if True:
    dcp_adt_path = "/arm-io/dcp"
    dcp_dart_adt_path = "/arm-io/dart-dcp"
    disp0_dart_adt_path = "/arm-io/dart-disp0"
else:
    dcp_adt_path = "/arm-io/dcpext"
    dcp_dart_adt_path = "/arm-io/dart-dcpext"
    disp0_dart_adt_path = "/arm-io/dart-dispext0"

trace_device(dcp_adt_path, True, ranges=[1])

DARTTracer = DARTTracer._reloadcls()
ASCTracer = ASCTracer._reloadcls()

iomon = RegMonitor(hv.u, ascii=True)

class AFKRingBufSniffer(AFKRingBuf):
    def __init__(self, ep, state, base, size):
        super().__init__(ep, base, size)
        self.state = state
        self.rptr = getattr(state, "rptr", 0)

    def update_rptr(self, rptr):
        self.state.rptr = rptr

    def update_wptr(self):
        raise NotImplementedError()

    def get_wptr(self):
        return struct.unpack("<I", self.read_buf(2 * self.BLOCK_SIZE, 4))[0]

    def read_buf(self, off, size):
        return self.ep.dart.ioread(0, self.base + off, size)

class AFKEp(EP):
    BASE_MESSAGE = AFKEPMessage

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)
        self.txbuf = None
        self.rxbuf = None
        self.state.txbuf = EPState()
        self.state.rxbuf = EPState()
        self.state.shmem_iova = None
        self.state.txbuf_info = None
        self.state.rxbuf_info = None
        self.state.verbose = 1

    def start(self):
        #self.add_mon()
        self.create_bufs()

    def create_bufs(self):
        if not self.state.shmem_iova:
            return
        if not self.txbuf and self.state.txbuf_info:
            off, size = self.state.txbuf_info
            self.txbuf = AFKRingBufSniffer(self, self.state.txbuf,
                                           self.state.shmem_iova + off, size)
        if not self.rxbuf and self.state.rxbuf_info:
            off, size = self.state.rxbuf_info
            self.rxbuf = AFKRingBufSniffer(self, self.state.rxbuf,
                                           self.state.shmem_iova + off, size)

    def add_mon(self):
        if self.state.shmem_iova:
            iomon.add(self.state.shmem_iova, 32768,
                      name=f"{self.name}.shmem@{self.state.shmem_iova:08x}", offset=0)

    Init =          msg_log(0x80, DIR.TX)
    Init_Ack =      msg_log(0xa0, DIR.RX)

    GetBuf =        msg_log(0x89, DIR.RX)

    Shutdown =      msg_log(0xc0, DIR.TX)
    Shutdown_Ack =  msg_log(0xc1, DIR.RX)

    @msg(0xa1, DIR.TX, AFKEP_GetBuf_Ack)
    def GetBuf_Ack(self, msg):
        self.state.shmem_iova = msg.DVA
        self.txbuf = None
        self.rxbuf = None
        self.state.txbuf = EPState()
        self.state.rxbuf = EPState()
        self.state.txbuf_info = None
        self.state.rxbuf_info = None
        #self.add_mon()

    @msg(0xa2, DIR.TX, AFKEP_Send)
    def Send(self, msg):
        for data in self.txbuf.read():
            if self.state.verbose >= 3:
                self.log(f">TX rptr={self.txbuf.state.rptr:#x}")
                chexdump(data, print_fn=self.log)
            self.handle_ipc(data, dir=">")
        return True

    Hello =         msg_log(0xa3, DIR.TX)

    @msg(0x85, DIR.RX, AFKEPMessage)
    def Recv(self, msg):
        for data in self.rxbuf.read():
            if self.state.verbose >= 3:
                self.log(f"<RX rptr={self.rxbuf.state.rptr:#x}")
                chexdump(data, print_fn=self.log)
            self.handle_ipc(data, dir="<")
        return True

    def handle_ipc(self, data, dir=None):
        pass

    @msg(0x8a, DIR.RX, AFKEP_InitRB)
    def InitTX(self, msg):
        off = msg.OFFSET * AFKRingBuf.BLOCK_SIZE
        size = msg.SIZE * AFKRingBuf.BLOCK_SIZE
        self.state.txbuf_info = (off, size)
        self.create_bufs()

    @msg(0x8b, DIR.RX, AFKEP_InitRB)
    def InitRX(self, msg):
        off = msg.OFFSET * AFKRingBuf.BLOCK_SIZE
        size = msg.SIZE * AFKRingBuf.BLOCK_SIZE
        self.state.rxbuf_info = (off, size)
        self.create_bufs()

class SilentEp(AFKEp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state.verbose = 0

    def log(self, msg):
        pass

def epic_service_cmd(group, cmd):
    def f(x):
        x.is_cmd = True
        x.group = group
        x.cmd = cmd
        return x
    return f

def epic_service_reply(group, cmd):
    def f(x):
        x.is_reply = True
        x.group = group
        x.cmd = cmd
        return x
    return f

class EPICServiceTracer(Reloadable):
    def __init__(self, tracer, ep, key):
        self.tracer = tracer
        self.ep = ep
        self.key = key

        self.cmdmap = {}
        self.replymap = {}
        for name in dir(self):
            i = getattr(self, name)
            if not callable(i):
                continue
            if getattr(i, "is_cmd", False):
                self.cmdmap[i.group, i.cmd] = getattr(self, name)
            if getattr(i, "is_reply", False):
                self.replymap[i.group, i.cmd] = getattr(self, name)

    def log(self, msg):
        self.ep.log(f"[{self.key}] {msg}")

    def init(self, props):
        pass

    def handle_cmd(self, sgroup, scmd, sdata):
        cmdfn = self.cmdmap.get((sgroup, scmd), None)
        if cmdfn:
            cmdfn(sdata)
        else:
            self.log(f"> unknown group {sgroup}; command {scmd}")
            if sdata:
                chexdump(sdata, print_fn=self.log)

    def handle_reply(self, sgroup, scmd, sdata):
        replyfn = self.replymap.get((sgroup, scmd), None)
        if replyfn:
            replyfn(sdata)
        else:
            self.log(f"< unknown group {sgroup}; command {scmd}")
            if sdata:
                chexdump(sdata, print_fn=self.log)

    @epic_service_cmd(4, 4)
    def getLocation(self, data):
        self.log("> getLocation")
    @epic_service_reply(4, 4)
    def getLocation_reply(self, data):
        self.log("< getLocation")

    @epic_service_cmd(4, 5)
    def getUnit(self, data):
        self.log("> getUnit")
    @epic_service_reply(4, 5)
    def getUnit_reply(self, data):
        self.log("< getUnit")

    @epic_service_cmd(4, 6)
    def open(self, data):
        self.log("> open")
    @epic_service_reply(4, 6)
    def open_reply(self, data):
        self.log("< open")

    @epic_service_cmd(4, 7)
    def close(self, data):
        self.log("> close")
    @epic_service_reply(4, 7)
    def close_reply(self, data):
        self.log("< close")

class EPICEp(AFKEp):
    SERVICES = []

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)

        self.serv_map = {}
        self.chan_map = {}
        self.serv_names = {}
        for i in self.SERVICES:
            self.serv_names[i.NAME] = i

    def handle_ipc(self, data, dir=None):
        fd = BytesIO(data)
        hdr = EPICHeader.parse_stream(fd)
        sub = EPICSubHeader.parse_stream(fd)

        if sub.category == EPICCategory.REPORT:
            self.handle_report(hdr, sub, fd)
        if sub.category == EPICCategory.NOTIFY:
            self.handle_notify(hdr, sub, fd)
        elif sub.category == EPICCategory.REPLY:
            self.handle_reply(hdr, sub, fd)
        elif sub.category == EPICCategory.COMMAND:
            self.handle_cmd(hdr, sub, fd)
        else:
            self.log(f"{dir}Ch {hdr.channel} Type {hdr.type} Ver {hdr.version} Tag {hdr.seq}")
            self.log(f"  Len {sub.length} Ver {sub.version} Cat {sub.category} Type {sub.type:#x} Seq {sub.seq}")
            chexdump(data, print_fn=self.log)

    def handle_report_init(self, hdr, sub, fd):
            init = EPICAnnounce.parse_stream(fd)
            self.log(f"Init: {init.name}")
            self.log(f"  Props: {init.props}")

            if not init.props:
                init.props = {}

            name = init.props.get("EPICName", init.name)
            key = name + str(init.props.get("EPICUnit", ""))
            self.log(f"New service: {key} on channel {hdr.channel}")

            srv_cls = self.serv_names.get(name, EPICServiceTracer)
            srv = srv_cls(self.tracer, self, key)
            srv.init(init.props)
            srv.chan = hdr.channel
            self.chan_map[hdr.channel] = srv
            self.serv_map[key] = srv

    def handle_report(self, hdr, sub, fd):
        if sub.type == 0x30:
            self.handle_report_init(hdr, sub, fd)
        else:
            self.log(f"Report {sub.type:#x}")
            chexdump(fd.read(), print_fn=self.log)

    def handle_notify(self, hdr, sub, fd):
        self.log(f"Notify:")
        chexdump(fd.read(), print_fn=self.log)

    def handle_reply(self, hdr, sub, fd):
        if sub.inline_len:
            payload = fd.read()
            self.log("Inline payload:")
            chexdump(payload, print_fn=self.log)
        else:
            cmd = EPICCmd.parse_stream(fd)
            if not cmd.rxbuf:
                self.log(f"Response {sub.type:#x}: {cmd.retcode:#x}")
                return

            data = self.dart.ioread(0, cmd.rxbuf, cmd.rxlen)
            rgroup, rcmd, rlen, rmagic = struct.unpack("<2xHIII", data[:16])
            if rmagic != 0x69706378:
                self.log("Warning: Invalid EPICStandardService response magic")

            srv = self.chan_map.get(hdr.channel, None)
            if srv:
                srv.handle_reply(rgroup, rcmd, data[64:64+rlen] if rlen else None)
            else:
                self.log(f"[???] < group {rgroup} command {rcmd}")
                chexdump(data[64:64+rlen], print_fn=lambda msg: self.log(f"[???] {msg}"))

    def handle_cmd(self, hdr, sub, fd):
        cmd = EPICCmd.parse_stream(fd)
        payload = fd.read()

        if sub.type == 0xc0 and cmd.txbuf:
            data = self.dart.ioread(0, cmd.txbuf, cmd.txlen)
            sgroup, scmd, slen, sfooter  = struct.unpack("<2xHIII48x", data[:64])
            sdata = data[64:64+slen] if slen else None

            srv = self.chan_map.get(hdr.channel, None)
            if srv:
                srv.handle_cmd(sgroup, scmd, sdata)
            else:
                self.log(f"[???] > group {sgroup} command {scmd}")
                chexdump(data[64:64+slen], print_fn=lambda msg: self.log(f"[???] {msg}"))
        else:
            self.log(f"Command {sub.type:#x}: {cmd.retcode:#x}")
            if payload:
                chexdump(payload, print_fn=self.log)
            if cmd.txbuf:
                self.log(f"TX buf @ {cmd.txbuf:#x} ({cmd.txlen:#x} bytes):")
                chexdump(self.dart.ioread(0, cmd.txbuf, cmd.txlen), print_fn=self.log)

KNOWN_MSGS = {
    "A000": "IOMFB::UPPipeAP_H13P::late_init_signal()",
    "A001": "IOMFB::UPPipeAP_H13P::init_ipa(unsigned long long, unsigned long)",
    "A002": "IOMFB::UPPipeAP_H13P::alss_supported()",
    "A003": "IOMFB::UPPipeAP_H13P::reset_dsc()",
    "A004": "IOMFB::UPPipeAP_H13P::display_edr_factor_changed(float)",
    "A005": "IOMFB::UPPipeAP_H13P::set_contrast(float)",
    "A006": "IOMFB::UPPipeAP_H13P::set_csc_mode(IOMFB_CSCMode)",
    "A007": "IOMFB::UPPipeAP_H13P::set_op_mode(IOMFB_CSCMode)",
    "A008": "IOMFB::UPPipeAP_H13P::set_op_gamma_mode(IOMFB_TFMode)",
    "A009": "IOMFB::UPPipeAP_H13P::set_video_out_mode(IOMFB_Output_Mode)",
    "A010": "IOMFB::UPPipeAP_H13P::set_meta_allowed(bool)",
    "A011": "IOMFB::UPPipeAP_H13P::set_tunneled_color_mode(bool)",
    "A012": "IOMFB::UPPipeAP_H13P::set_bwr_line_time_us(double)",
    "A013": "IOMFB::UPPipeAP_H13P::performance_feedback(double)",
    "A014": "IOMFB::UPPipeAP_H13P::notify_swap_complete(unsigned int)",
    "A015": "IOMFB::UPPipeAP_H13P::is_run_mode_change_pending() const",
    "A016": "IOMFB::UPPipeAP_H13P::ready_for_run_mode_change(IOMFB::AppleRegisterStream*)",
    "A017": "IOMFB::UPPipeAP_H13P::set_thermal_throttle_cap(unsigned int)",
    "A018": "IOMFB::UPPipeAP_H13P::emergency_shutdown_normal_mode(IOMFB::AppleRegisterStream*)",
    "A019": "IOMFB::UPPipeAP_H13P::set_target_run_mode(IOMFB::AppleRegisterStream*)",
    "A020": "IOMFB::UPPipeAP_H13P::rt_bandwidth_setup()",
    "A021": "IOMFB::UPPipeAP_H13P::rt_bandwidth_update(IOMFB::AppleRegisterStream*, float, float, bool, bool)",
    "A022": "IOMFB::UPPipeAP_H13P::rt_bandwidth_update_downgrade(IOMFB::AppleRegisterStream*)",
    "A023": "IOMFB::UPPipeAP_H13P::rt_bandwidth_write_update(IOMFB::AppleRegisterStream*, RealtimeBandwithWritebackBlock, bool)",
    "A024": "IOMFB::UPPipeAP_H13P::cif_blending_eco_present()",
    "A025": "IOMFB::UPPipeAP_H13P::request_bic_update()",
    "A026": "IOMFB::UPPipeAP_H13P::early_power_off_warning(IOMFB::AppleRegisterStream*)",
    "A027": "IOMFB::UPPipeAP_H13P::get_max_frame_size(unsigned int*, unsigned int*)",
    "A028": "IOMFB::UPPipeAP_H13P::shadow_FIFO_empty(IOMFB::AppleRegisterStream*) const",
    "A029": "IOMFB::UPPipeAP_H13P::setup_video_limits()",
    "A030": "IOMFB::UPPipeAP_H13P::can_program_swap() const",
    "A031": "IOMFB::UPPipeAP_H13P::in_auto_mode() const",
    "A032": "IOMFB::UPPipeAP_H13P::push_black_frame(IOMFB::AppleRegisterStream*)",
    "A033": "IOMFB::UPPipeAP_H13P::read_crc(Notify_Info_Index, unsigned int)",
    "A034": "IOMFB::UPPipeAP_H13P::update_notify_clients_dcp(unsigned int const*)",
    "A035": "IOMFB::UPPipeAP_H13P::is_hilo() const",
    "A036": "IOMFB::UPPipeAP_H13P::apt_supported() const",
    "A037": "IOMFB::UPPipeAP_H13P::get_dfb_info(unsigned int*, unsigned long long*, unsigned int*)",
    "A038": "IOMFB::UPPipeAP_H13P::get_dfb_compression_info(unsigned int*)",
    "A039": "IOMFB::UPPipeAP_H13P::get_frame_done_time() const",
    "A040": "IOMFB::UPPipeAP_H13P::get_performance_headroom() const",
    "A041": "IOMFB::UPPipeAP_H13P::are_stats_active() const",
    "A042": "IOMFB::UPPipeAP_H13P::supports_odd_h_blanking() const",
    "A043": "IOMFB::UPPipeAP_H13P::is_first_hw_version() const",
    "A044": "IOMFB::UPPipeAP_H13P::set_blendout_CSC_mode()",

    "A100": "IOMFB::UPPipe2::get_gamma_table_gated(IOMFBGammaTable*)",
    "A101": "IOMFB::UPPipe2::set_gamma_table_gated(IOMFBGammaTable const*)",
    "A102": "IOMFB::UPPipe2::test_control(IOMFB_TC_Cmd, unsigned int)",
    "A103": "IOMFB::UPPipe2::get_config_frame_size(unsigned int*, unsigned int*) const",
    "A104": "IOMFB::UPPipe2::set_config_frame_size(unsigned int, unsigned int) const",
    "A105": "IOMFB::UPPipe2::program_config_frame_size() const",
    "A106": "IOMFB::UPPipe2::read_blend_crc() const",
    "A107": "IOMFB::UPPipe2::read_config_crc() const",
    "A108": "IOMFB::UPPipe2::disable_wpc_calibration(bool)",
    "A109": "IOMFB::UPPipe2::vftg_is_running(IOMFB::AppleRegisterStream*) const",
    "A110": "IOMFB::UPPipe2::vftg_debug(IOMFB::AppleRegisterStream*, unsigned int) const",
    "A111": "IOMFB::UPPipe2::vftg_set_color_channels(unsigned int, unsigned int, unsigned int)",
    "A112": "IOMFB::UPPipe2::set_color_filter_scale(int)",
    "A113": "IOMFB::UPPipe2::set_corner_temps(int const*)",
    "A114": "IOMFB::UPPipe2::reset_aot_enabled() const",
    "A115": "IOMFB::UPPipe2::aot_enabled() const",
    "A116": "IOMFB::UPPipe2::aot_active() const",
    "A117": "IOMFB::UPPipe2::set_timings_enabled(IOMFB::AppleRegisterStream*, bool)",
    "A118": "IOMFB::UPPipe2::get_frame_size(IOMFB::AppleRegisterStream*, unsigned int*, unsigned int*)",
    "A119": "IOMFB::UPPipe2::set_block(unsigned long long, unsigned int, unsigned int, unsigned long long const*, unsigned int, unsigned char const*, unsigned long, bool)",
    "A121": "IOMFB::UPPipe2::get_buf_block(unsigned long long, unsigned int, unsigned int, unsigned long long const*, unsigned int, unsigned char const*, unsigned long, bool)",
    "A122": "IOMFB::UPPipe2::get_matrix(IOMFB_MatrixLocation, IOMFBColorFixedMatrix*) const",
    "A123": "IOMFB::UPPipe2::set_matrix(IOMFB_MatrixLocation, IOMFBColorFixedMatrix const*)",
    "A124": "IOMFB::UPPipe2::get_internal_timing_attributes_gated(IOMFB::RefreshTimingAttributes*) const",
    "A125": "IOMFB::UPPipe2::display_edr_factor_changed(float)",
    "A126": "IOMFB::UPPipe2::set_contrast(float)",
    "A127": "IOMFB::UPPipe2::p3_to_disp_cs(float const*, float const (*) [2])",
    "A128": "IOMFB::UPPipe2::max_panel_brightness() const",
    "A129": "IOMFB::UPPipe2::swap_flush_stream_replay(IOMFB::AppleRegisterStream*)",
    "A130": "IOMFB::UPPipe2::init_ca_pmu()",
    "A131": "IOMFB::UPPipe2::pmu_service_matched()",
    "A132": "IOMFB::UPPipe2::backlight_service_matched()",

    "A200": "IOMFB::PropRelay::setBool(IOMFB::RuntimeProperty, bool)",
    "A201": "IOMFB::PropRelay::setInt(IOMFB::RuntimeProperty, unsigned int)",
    "A202": "IOMFB::PropRelay::setFx(IOMFB::RuntimeProperty, int)",
    "A203": "IOMFB::PropRelay::setPropDynamic(IOMFB::RuntimeProperty, unsigned int)",
    "A204": "IOMFB::PropRelay::getBool(IOMFB::RuntimeProperty)",
    "A205": "IOMFB::PropRelay::getInt(IOMFB::RuntimeProperty)",
    "A206": "IOMFB::PropRelay::getFx(IOMFB::RuntimeProperty)",

    "A350": "UnifiedPipeline2::displayHeight()",
    "A351": "UnifiedPipeline2::displayWidth()",
    "A352": "UnifiedPipeline2::applyProperty(unsigned int, unsigned int)",
    "A353": "UnifiedPipeline2::get_system_type() const",
    "A354": "UnifiedPipeline2::headless() const",
    "A355": "UnifiedPipeline2::export_idle_method(unsigned int)",
    "A357": "UnifiedPipeline2::set_create_DFB()",
    "A358": "UnifiedPipeline2::vi_set_temperature_hint()",

    "A400": "IOMobileFramebufferAP::free_signal()",
    "A401": "IOMobileFramebufferAP::start_signal()",
    "A402": "IOMobileFramebufferAP::stop_signal()",
    "A403": "IOMobileFramebufferAP::systemWillShutdown()",
    "A404": "IOMobileFramebufferAP::swap_begin()",
    "A405": "IOMobileFramebufferAP::rotate_surface(unsigned int, unsigned int, unsigned int)",
    "A406": "IOMobileFramebufferAP::get_framebuffer_id()",
    "A407": "IOMobileFramebufferAP::swap_start(unsigned int*, IOUserClient*)",
    "A408": "IOMobileFramebufferAP::swap_submit_dcp(IOMFBSwapRec const*, IOSurface**, unsigned int const*, bool, double, unsigned int, bool*)",
    "A409": "IOMobileFramebufferAP::swap_signal(unsigned int, unsigned int)",
    "A410": "IOMobileFramebufferAP::set_display_device(unsigned int)",
    "A411": "IOMobileFramebufferAP::is_main_display() const",
    "A412": "IOMobileFramebufferAP::set_digital_out_mode(unsigned int, unsigned int)",
    "A413": "IOMobileFramebufferAP::get_digital_out_state(unsigned int*)",
    "A414": "IOMobileFramebufferAP::get_display_area(DisplayArea*)",
    "A415": "IOMobileFramebufferAP::set_tvout_mode(unsigned int)",
    "A416": "IOMobileFramebufferAP::set_tvout_signaltype(unsigned int)",
    "A417": "IOMobileFramebufferAP::set_wss_info(unsigned int, unsigned int)",
    "A418": "IOMobileFramebufferAP::set_content_flags(unsigned int)",
    "A419": "IOMobileFramebufferAP::get_gamma_table(IOMFBGammaTable*)",
    "A420": "IOMobileFramebufferAP::set_gamma_table(IOMFBGammaTable*)",
    "A421": "IOMobileFramebufferAP::get_matrix(unsigned int, unsigned long long (*) [3][3]) const",
    "A422": "IOMobileFramebufferAP::set_matrix(unsigned int, unsigned long long const (*) [3][3])",
    "A423": "IOMobileFramebufferAP::set_contrast(float*)",
    "A424": "IOMobileFramebufferAP::set_white_on_black_mode(unsigned int)",
    "A425": "IOMobileFramebufferAP::set_color_remap_mode(DisplayColorRemapMode)",
    "A426": "IOMobileFramebufferAP::get_color_remap_mode(DisplayColorRemapMode*) const",
    "A427": "IOMobileFramebufferAP::setBrightnessCorrection(unsigned int)",
    "A428": "IOMobileFramebufferAP::temp_queue_swap_cancel(unsigned int)",
    "A429": "IOMobileFramebufferAP::swap_cancel(unsigned int)",
    "A430": "IOMobileFramebufferAP::swap_cancel_all_dcp(unsigned long long)",
    "A431": "IOMobileFramebufferAP::surface_is_replaceable(unsigned int, bool*)",
    "A432": "IOMobileFramebufferAP::kernel_tests(IOMFBKernelTestsArguments*)",
    "A433": "IOMobileFramebufferAP::splc_set_brightness(unsigned int)",
    "A434": "IOMobileFramebufferAP::splc_get_brightness(unsigned int*)",
    "A435": "IOMobileFramebufferAP::set_block_dcp(task*, unsigned int, unsigned int, unsigned long long const*, unsigned int, unsigned char const*, unsigned long)",
    "A436": "IOMobileFramebufferAP::get_block_dcp(task*, unsigned int, unsigned int, unsigned long long const*, unsigned int, unsigned char*, unsigned long) const",
    "A438": "IOMobileFramebufferAP::swap_set_color_matrix(IOMFBColorFixedMatrix*, IOMFBColorMatrixFunction, unsigned int)",
    "A439": "IOMobileFramebufferAP::set_parameter_dcp(IOMFBParameterName, unsigned long long const*, unsigned int)",
    "A440": "IOMobileFramebufferAP::display_width() const",
    "A441": "IOMobileFramebufferAP::display_height() const",
    "A442": "IOMobileFramebufferAP::get_display_size(unsigned int*, unsigned int*) const",
    "A443": "IOMobileFramebufferAP::do_create_default_frame_buffer() const",
    "A444": "IOMobileFramebufferAP::printRegs()",
    "A445": "IOMobileFramebufferAP::enable_disable_dithering(unsigned int)",
    "A446": "IOMobileFramebufferAP::set_underrun_color(unsigned int)",
    "A447": "IOMobileFramebufferAP::enable_disable_video_power_savings(unsigned int)",
    "A448": "IOMobileFramebufferAP::set_video_dac_gain(unsigned int)",
    "A449": "IOMobileFramebufferAP::set_line21_data(unsigned int)",
    "A450": "IOMobileFramebufferAP::enableInternalToExternalMirroring(bool)",
    "A451": "IOMobileFramebufferAP::getExternalMirroringCapability(IOMFBMirroringCapability*)",
    "A452": "IOMobileFramebufferAP::setRenderingAngle(float*)",
    "A453": "IOMobileFramebufferAP::setOverscanSafeRegion(IOMFBOverscanSafeRect*)",
    "A454": "IOMobileFramebufferAP::first_client_open()",
    "A455": "IOMobileFramebufferAP::last_client_close_dcp(unsigned int*)",
    "A456": "IOMobileFramebufferAP::writeDebugInfo(unsigned long)",
    "A457": "IOMobileFramebufferAP::flush_debug_flags(unsigned int)",
    "A458": "IOMobileFramebufferAP::io_fence_notify(unsigned int, unsigned int, unsigned long long, IOMFBStatus)",
    "A459": "IOMobileFramebufferAP::swap_wait_dcp(bool, unsigned int, unsigned int, unsigned int)",
    "A460": "IOMobileFramebufferAP::setDisplayRefreshProperties()",
    "A461": "IOMobileFramebufferAP::exportProperty(unsigned int, unsigned int)",
    "A462": "IOMobileFramebufferAP::applyProperty(unsigned int, unsigned int)",
    "A463": "IOMobileFramebufferAP::flush_supportsPower(bool)",
    "A464": "IOMobileFramebufferAP::abort_swaps_dcp(IOMobileFramebufferUserClient*)",
    "A465": "IOMobileFramebufferAP::swap_signal_gated(unsigned int, unsigned int)",
    "A466": "IOMobileFramebufferAP::update_dfb(IOSurface*, unsigned int, unsigned int, unsigned long long)",
    "A467": "IOMobileFramebufferAP::update_dfb(IOSurface*)",
    "A468": "IOMobileFramebufferAP::setPowerState(unsigned long, bool, unsigned int*)",
    "A469": "IOMobileFramebufferAP::isKeepOnScreen() const",
    "A470": "IOMobileFramebufferAP::resetStats()",
    "A471": "IOMobileFramebufferAP::set_has_frame_swap_function(bool)",
    "A472": "IOMobileFramebufferAP::getPerformanceStats(unsigned int*, unsigned int*)",

    "D000": "bool IOMFB::UPPipeAP_H13P::did_boot_signal()",
    "D001": "bool IOMFB::UPPipeAP_H13P::did_power_on_signal()",
    "D002": "void IOMFB::UPPipeAP_H13P::will_power_off_signal()",
    "D003": "void IOMFB::UPPipeAP_H13P::rt_bandwidth_setup_ap(inout rt_bw_config_t*)",
    "D004": "void IOMFB::UPPipeAP_H13P::mcc_report_replay(bool, unsigned int)",
    "D005": "void IOMFB::UPPipeAP_H13P::mcc_report_bics(bool, unsigned int)",

    "D100": "void UnifiedPipeline2::match_pmu_service()",
    #"D101": "", # get some uint32_t, inlined
    "D102": "void UnifiedPipeline2::set_number_property(char const*, unsigned int)",
    "D103": "void UnifiedPipeline2::set_boolean_property(char const*, bool)",
    "D104": "void UnifiedPipeline2::set_string_property(char const*, char const*)",
    "D105": "IOReturn IOService::acknowledgeSetPowerState()",
    "D106": "void IORegistryEntry::removeProperty(char const*)",
    "D107": "bool UnifiedPipeline2::create_provider_service",
    "D108": "bool UnifiedPipeline2::create_product_service()",
    "D109": "bool UnifiedPipeline2::create_PMU_service()",
    "D110": "bool UnifiedPipeline2::create_iomfb_service()",
    "D111": "bool UnifiedPipeline2::create_backlight_service()",
    "D112": "void UnifiedPipeline2::set_idle_caching_state_ap(IdleCachingState, unsigned int)",
    "D113": "bool UnifiedPipeline2::upload_trace_start(IOMFB::FrameInfoBuffer::FrameInfoConstants const*)",
    "D114": "bool UnifiedPipeline2::upload_trace_chunk(IOMFB::FrameInfoBuffer::FrameInfoData const*, unsigned int, unsigned int)",
    "D115": "bool UnifiedPipeline2::upload_trace_end(char const*)",
    "D116": "bool UnifiedPipeline2::start_hardware_boot()",
    "D117": "bool UnifiedPipeline2::is_dark_boot()",
    "D118": "bool UnifiedPipeline2::is_waking_from_hibernate()",
    "D119": "bool UnifiedPipeline2::detect_fastsim()",
    "D120": "bool UnifiedPipeline2::read_edt_data(char const*, unsigned int, unsigned int*) const",
    "D121": "bool UnifiedPipeline2::read_edt_string(char const*, char*, unsigned int*) const",
    "D122": "bool UnifiedPipeline2::setDCPAVPropStart(unsigned int)",
    "D123": "bool UnifiedPipeline2::setDCPAVPropChunk(unsigned char const*, unsigned int, unsigned int)",
    "D124": "bool UnifiedPipeline2::setDCPAVPropEnd(char const*)",

    "D200": "uint64_t IOMFB::UPPipe2::get_default_idle_caching_method()",
    "D201": "IOMFBStatus IOMFB::UPPipe2::map_buf(IOMFB::BufferDescriptor*, unsigned long*, unsigned long long*, bool)",
    "D202": "void IOMFB::UPPipe2::unmap_buf(IOMFB::BufferDescriptor*, unsigned long, unsigned long long, bool)",
    "D203": "bool IOMFB::UPPipe2::aot_supported_peek()",
    "D204": "uint64_t IOMFB::UPPipe2::get_ideal_screen_space()",
    "D205": "bool IOMFB::UPPipe2::read_carveout(unsigned char*, unsigned int, unsigned int) const",
    "D206": "bool IOMFB::UPPipe2::match_pmu_service()",
    "D207": "bool IOMFB::UPPipe2::match_backlight_service()",
    "D208": "uint64_ IOMFB::UPPipe2::get_calendar_time_ms()",
    "D209": "void IOMFB::UPPipe2::plc_enable(bool)",
    "D210": "void IOMFB::UPPipe2::plc_init()",
    "D211": "void IOMFB::UPPipe2::update_backlight_factor_prop(int)",

    "D300": "void IOMFB::PropRelay::publish(IOMFB::RuntimeProperty, unsigned int)",

    "D400": "void IOMFB::ServiceRelay::get_property(unsigned int, in char const[0x40], out unsigned char[0x200], inout unsigned int*)",
    "D401": "bool IOMFB::ServiceRelay::get_uint_prop(unsigned int, in char const[0x40], inout unsigned long long*)",
    "D402": "void IOMFB::ServiceRelay::set_uint_prop(unsigned int, in char const[0x40], unsigned long long)",
    "D403": "bool IOMFB::ServiceRelay::get_uint_prop(unsigned int, in char const[0x40], inout unsigned int*)",
    "D404": "void IOMFB::ServiceRelay::set_uint_prop(unsigned int, in char const[0x40], unsigned int)",
    "D405": "bool IOMFB::ServiceRelay::get_fx_prop(unsigned int, in char const[0x40], inout int*)",
    "D406": "void IOMFB::ServiceRelay::set_fx_prop(unsigned int, in char const[0x40], int)",
    "D407": "void IOMFB::ServiceRelay::set_bool_prop(unsigned int, in char const[0x40], bool)",
    "D408": "unsigned long long IOMFB::ServiceRelay::getClockFrequency(unsigned int, unsigned int)",
    "D409": "IOMFBStatus IOMFB::ServiceRelay::enableDeviceClock(unsigned int, unsigned int, unsigned int)",
    "D410": "IOMFBStatus IOMFB::ServiceRelay::enableDevicePower(unsigned int, unsigned int, inout unsigned int*, unsigned int)",
    "D411": "IOMFBStatus IOMFB::ServiceRelay::mapDeviceMemoryWithIndex(unsigned int, unsigned int, unsigned int, inout unsigned long*, inout unsigned long long*)",
    "D412": "bool IOMFB::ServiceRelay::setProperty(unsigned int, OSString<0x40> const*, OSArray const*)",
    "D413": "bool IOMFB::ServiceRelay::setProperty(unsigned int, OSString<0x40> const*, OSDictionary const*)",
    "D414": "bool IOMFB::ServiceRelay::setProperty(unsigned int, OSString<0x40> const*, OSNumber const*)",
    "D415": "bool IOMFB::ServiceRelay::setProperty(unsigned int, OSString<0x40> const*, OSBoolean const*)",
    "D416": "bool IOMFB::ServiceRelay::setProperty(unsigned int, OSString<0x40> const*, OSString const*)",
    "D417": "bool IOMFB::ServiceRelay::setProperty(unsigned int, char const[0x40], OSArray const*)",
    "D418": "bool IOMFB::ServiceRelay::setProperty(unsigned int, char const[0x40], OSDictionary const*)",
    "D419": "bool IOMFB::ServiceRelay::setProperty(unsigned int, char const[0x40], OSNumber const*)",
    "D420": "bool IOMFB::ServiceRelay::setProperty(unsigned int, char const[0x40], OSBoolean const*)",
    "D421": "bool IOMFB::ServiceRelay::setProperty(unsigned int, char const[0x40], OSString const*)",
    "D422": "bool IOMFB::ServiceRelay::setProperty(unsigned int, char const[0x40], bool)",
    "D423": "void IOMFB::ServiceRelay::removeProperty(unsigned int, char const[0x40])",
    "D424": "void IOMFB::ServiceRelay::removeProperty(unsigned int, OSString<0x40> const*)",

    "D450": "bool IOMFB::MemDescRelay::from_id(unsigned int, unsigned long*, unsigned long*, unsigned long long*)",
    "D451": "MemDescRelay::desc_id_t IOMFB::MemDescRelay::allocate_buffer(unsigned int, unsigned long long, unsigned int, unsigned long*, unsigned long*, unsigned long long*)",
    "D452": "MemDescRelay::desc_id_t IOMFB::MemDescRelay::map_physical(unsigned long long, unsigned long long, unsigned int, unsigned long*, unsigned long long*)",
    "D453": "MemDescRelay::desc_id_t IOMFB::MemDescRelay::withAddressRange(unsigned long long, unsigned long long, unsigned int, task*, unsigned long*, unsigned long long*)",
    "D454": "IOMFBStatus IOMFB::MemDescRelay::prepare(unsigned int, unsigned int)",
    "D455": "IOMFBStatus IOMFB::MemDescRelay::complete(unsigned int, unsigned int)",
    "D456": "bool IOMFB::MemDescRelay::release_descriptor(unsigned int)",

    "D500": "IOMFBStatus IOMFB::PlatformFunctionRelay::allocate_record(unsigned int, char const*, unsigned int, bool)",
    "D501": "IOMFBStatus IOMFB::PlatformFunctionRelay::release_record(unsigned int)",
    "D502": "IOMFBStatus IOMFB::PlatformFunctionRelay::callFunctionLink(unsigned int, unsigned long, unsigned long, unsigned long)",

    "D550": "bool IORegistryEntry::setProperty(OSString *, OSArray *)",
    "D551": "bool IORegistryEntry::setProperty(OSString *, IOMFB::AFKArray *)",
    "D552": "bool IORegistryEntry::setProperty(OSString *, OSDictionary *)",
    "D553": "bool IORegistryEntry::setProperty(OSString *, IOMFB::AFKDictionary *)",
    "D554": "bool IORegistryEntry::setProperty(OSString *, OSNumber *)",
    "D555": "bool IORegistryEntry::setProperty(OSString *, IOMFB::AFKNumber *)",
    "D556": "bool IORegistryEntry::setProperty(OSString *, OSBoolean *)",
    "D557": "bool IORegistryEntry::setProperty(OSString *, OSString *)",
    "D558": "bool IORegistryEntry::setProperty(OSString *, IOMFB::AFKString *)",
    "D559": "bool IORegistryEntry::setProperty(char const*, OSArray *)",
    "D560": "bool IORegistryEntry::setProperty(char const*, IOMFB::AFKArray *)",
    "D561": "bool IORegistryEntry::setProperty(char const*, OSDictionary *)",
    "D562": "bool IORegistryEntry::setProperty(char const*, IOMFB::AFKDictionary *)",
    "D563": "bool IORegistryEntry::setProperty(char const*, OSNumber *)",
    "D564": "bool IORegistryEntry::setProperty(char const*, IOMFB::AFKNumber *)",
    "D565": "bool IORegistryEntry::setProperty(char const*, OSBoolean *)",
    "D566": "bool IORegistryEntry::setProperty(char const*, OSString *)",
    "D567": "bool IORegistryEntry::setProperty(char const*, IOMFB::AFKString *)",
    "D568": "bool IORegistryEntry::setProperty(char const*, char const*)",
    "D569": "bool IORegistryEntry::setProperty(char const*, bool)",
    "D570": "IOMFBStatus IOMobileFramebufferAP::setProperties(OSDictionary*)",
    "D571": "void IOMobileFramebufferAP::swapping_client_did_start(IOMobileFramebufferUserClient*)",
    "D572": "void IOMobileFramebufferAP::swapping_client_will_stop(IOMobileFramebufferUserClient*)",
    "D573": "IOMFBStatus IOMobileFramebufferAP::set_canvas_size(unsigned int, unsigned int)",
    "D574": "IOMFBStatus IOMobileFramebufferAP::powerUpDART(bool)",
    "D575": "IOMFBStatus IOMobileFramebufferAP::get_dot_pitch(unsigned int*)",
    "D576": "void IOMobileFramebufferAP::hotPlug_notify_gated(unsigned long long)",
    "D577": "void IOMobileFramebufferAP::powerstate_notify(bool, bool)",
    "D578": "bool IOMobileFramebufferAP::idle_fence_create(IdleCachingState)",
    "D579": "void IOMobileFramebufferAP::idle_fence_complete()",
    "D580": "void IOMobileFramebufferAP::idle_surface_release_ap()",
    "D581": "void IOMobileFramebufferAP::swap_complete_head_of_line(unsigned int, bool, unsigned int, bool)",
    "D582": "bool IOMobileFramebufferAP::create_default_fb_surface(unsigned int, unsigned int)",
    "D583": "bool IOMobileFramebufferAP::serializeDebugInfoCb(unsigned long, IOMFB::BufferDescriptor const*, unsigned int)",
    "D584": "void IOMobileFramebufferAP::clear_default_surface()",
    "D585": "void IOMobileFramebufferAP::swap_notify_gated(unsigned long long, unsigned long long, unsigned long long)",
    "D586": "void IOMobileFramebufferAP::swap_info_notify_dispatch(SwapInfoBlob const*)",
    "D587": "void IOMFBStatus IOMobileFramebufferAP::updateBufferMappingCount_gated(bool)",
    "D588": "void IOMobileFramebufferAP::resize_default_fb_surface_gated()",
    "D589": "void IOMobileFramebufferAP::swap_complete_ap_gated(unsigned int, bool, SwapCompleteData const*, SwapInfoBlob const*, unsigned int)",
    "D590": "void IOMobileFramebufferAP::batched_swap_complete_ap_gated(unsigned int*, unsigned int, bool, bool const*, SwapCompleteData const*)",
    "D591": "void IOMobileFramebufferAP::swap_complete_intent_gated(unsigned int, bool, IOMFBSwapRequestIntent, unsigned int, unsigned int)",
    "D592": "void IOMobileFramebufferAP::abort_swap_ap_gated(unsigned int)",
    "D593": "void IOMobileFramebufferAP::enable_backlight_message_ap_gated(bool)",
    "D594": "void IOMobileFramebufferAP::setSystemConsoleMode(bool)",
    "D595": "void IOMobileFramebufferAP::setSystemConsoleMode_gated(bool)",
    "D596": "bool IOMobileFramebufferAP::isDFBAllocated()",
    "D597": "bool IOMobileFramebufferAP::preserveContents()",
    "D598": "void IOMobileFramebufferAP::find_swap_function_gated()",

    "D700": "int IOMFB::DCPPowerManager::set_kernel_power_assert(bool, bool)",
}

# iboot interface
"""
0: setResource
1: setSurface
2: setPower
3: getHpdStatus
4: getTimingModes
5: getColorModes
6: setMode
7: setBrightness
8: rwBCONRegsRequest
9: setParameter
10: setMatrix
11: setProperty
12: getProperty
13: setBlock
14: getBlock
15: swapBegin
16: setSwapLayer
17: setSwapTimestamp
18: setSwapEnd
19: setSwapWait
20: setBrightnessCfg
21: setNamedProperty
22: getNamedProperty
"""

from m1n1.fw.dcp.dcpep import DCPMessage, DCPEp_SetShmem, CallContext, DCPEp_Msg

class DCPCallState:
    pass

class DCPCallChannel(Reloadable):
    def __init__(self, dcpep, name, buf, bufsize):
        self.dcpep = dcpep
        self.name = name
        self.buf = buf
        self.bufsize = bufsize
        self.log = self.dcpep.log
        self.state = self.dcpep.state

    def call(self, msg, dir):
        ident = f"{self.name}.{msg.OFF:x}"

        if any(msg.OFF == s.off for s in self.state.ch.get(self.name, [])):
            self.log(f"{dir}{self.name}.{msg.OFF:x} !!! Overlapping call ({msg})")
            assert False

        state = DCPCallState()

        data = self.dcpep.dart.ioread(0, self.state.shmem_iova + self.buf + msg.OFF, msg.LEN)
        tag = data[:4][::-1].decode("ascii")
        in_len, out_len = struct.unpack("<II", data[4:12])
        data_in = data[12:12 + in_len]

        state.off = msg.OFF
        state.tag = tag
        state.in_len = in_len
        state.out_addr = self.buf + msg.OFF + 12 + in_len
        state.out_len = out_len

        verb = self.dcpep.get_verbosity(tag)
        if verb >= 1:
            self.log(f"{dir}{self.name}.{msg.OFF:x} {tag}:{KNOWN_MSGS.get(tag, 'unk')} ({msg})")
        if verb >= 2:
            print(f"Message: {tag} ({KNOWN_MSGS.get(tag, 'unk')}): (in {in_len:#x}, out {out_len:#x})")
            if data_in:
                print(f"{dir} Input ({len(data_in):#x} bytes):")
                chexdump(data_in[:self.state.max_len])

        #if tag not in KNOWN_MSGS:
            #hv.run_shell()

        if self.state.dumpfile:
            dump = f"CALL {dir} {msg.value:#018x} {self.name} {state.off:#x} {state.tag} {in_len:#x} {out_len:#x} {data_in.hex()}\n"
            self.state.dumpfile.write(dump)
            self.state.dumpfile.flush()

        self.state.ch.setdefault(self.name, []).append(state)

    def ack(self, msg, dir):
        assert msg.LEN == 0

        states = self.state.ch.get(self.name, None)
        if not states:
            self.log(f"{dir}ACK {self.name}.{msg.OFF:x} !!! ACK without call ({msg})")
            return

        state = states[-1]

        if self.state.show_acks:
            self.log(f"{dir}ACK {self.name}.{msg.OFF:x} ({msg})")

        data_out = self.dcpep.dart.ioread(0, self.state.shmem_iova + state.out_addr, state.out_len)

        verb = self.dcpep.get_verbosity(state.tag)
        if verb >= 3 and state.out_len > 0:
            print(f"{dir}{self.name}.{msg.OFF:x} Output buffer ({len(data_out):#x} bytes):")
            chexdump(data_out[:self.state.max_len])

        if self.state.dumpfile:
            dump = f"ACK {dir} {msg.value:#018x} {self.name} {state.off:#x} {data_out.hex()}\n"
            self.state.dumpfile.write(dump)
            self.state.dumpfile.flush()

        states.pop()

class DCPEp(EP):
    BASE_MESSAGE = DCPMessage

    def __init__(self, tracer, epid):
        super().__init__(tracer, epid)
        self.state.shmem_iova = None
        self.state.show_globals = True
        self.state.show_acks = True
        self.state.max_len = 1024 * 1024
        self.state.verbosity = 3
        self.state.op_verb = {}
        self.state.ch = {}
        self.state.dumpfile = None

        self.ch_cb = DCPCallChannel(self, "CB", 0x60000, 0x8000)
        self.ch_cmd = DCPCallChannel(self, "CMD", 0, 0x8000)
        self.ch_async = DCPCallChannel(self, "ASYNC", 0x40000, 0x20000)
        self.ch_oobcb = DCPCallChannel(self, "OOBCB", 0x68000, 0x8000)
        self.ch_oobcmd = DCPCallChannel(self, "OOBCMD", 0x8000, 0x8000)

        self.cmd_ch = {
            CallContext.CB: self.ch_cmd,
            CallContext.CMD: self.ch_cmd,
            CallContext.ASYNC: None, # unknown
            CallContext.OOBCB: self.ch_oobcmd,
            CallContext.OOBCMD: self.ch_oobcmd,
        }

        self.cb_ch = {
            CallContext.CB: self.ch_cb,
            CallContext.CMD: None,
            CallContext.ASYNC: self.ch_async,
            CallContext.OOBCB: self.ch_oobcb,
            CallContext.OOBCMD: None,
        }

    def start(self):
        self.add_mon()

    def add_mon(self):
        if self.state.shmem_iova and self.state.show_globals:
            addr = self.state.shmem_iova + 0x80000
            iomon.add(addr, 128,
                      name=f"{self.name}.shmem@{addr:08x}", offset=addr)

            #addr = self.state.shmem_iova
            #iomon.add(addr, 0x80080,
                      #name=f"{self.name}.shmem@{addr:08x}", offset=addr)

    InitComplete = msg_log(1, DIR.RX)

    @msg(0, DIR.TX, DCPEp_SetShmem)
    def SetShmem(self, msg):
        self.log(f"Shared memory DVA: {msg.DVA:#x}")
        self.state.shmem_iova = msg.DVA & 0xffffffff
        self.add_mon()

    @msg(2, DIR.TX, DCPEp_Msg)
    def Tx(self, msg):
        if msg.ACK:
            self.cb_ch[msg.CTX].ack(msg, ">")
        else:
            self.cmd_ch[msg.CTX].call(msg, ">")

        if self.state.show_globals:
            iomon.poll()

        return True

    @msg(2, DIR.RX, DCPEp_Msg)
    def Rx(self, msg):
        self.log(msg)
        if msg.ACK:
            self.cmd_ch[msg.CTX].ack(msg, "<")
        else:
            self.cb_ch[msg.CTX].call(msg, "<")

        if self.state.show_globals:
            iomon.poll()

        return True

    def get_verbosity(self, tag):
        return self.state.op_verb.get(tag, self.state.verbosity)

    def set_verb_known(self, verb):
        for i in KNOWN_MSGS:
            if verb is None:
                self.state.op_verb.pop(i, None)
            else:
                self.state.op_verb[i] = verb

class SystemService(EPICEp):
    NAME = "system"

class TestService(EPICEp):
    NAME = "test"

class DCPExpertService(EPICEp):
    NAME = "dcpexpert"

class Disp0Service(EPICEp):
    NAME = "disp0"

class DCPAVControllerEpicTracer(EPICServiceTracer):
    NAME = "dcpav-controller-epic"

    @epic_service_cmd(0, 14)
    def getParticipatesPowerManagement(self, data):
        self.log("> getParticipatesPowerManagement")
    @epic_service_reply(0, 14)
    def getParticipatesPowerManagement_reply(self, data):
        self.log("< getParticipatesPowerManagement")
        chexdump(data, print_fn=self.log)

class DPAVController(EPICEp):
    NAME = "dpavctrl"
    SERVICES = [
        DCPAVControllerEpicTracer
    ]

class DPSACService(EPICEp):
    NAME = "dpsac"


class DCPDPDeviceEpicTracer(EPICServiceTracer):
    NAME = "dcpdp-device-epic"

    @epic_service_cmd(0, 15)
    def getDeviceMatchingData(self, data):
        self.log("> getDeviceMatchingData")
    @epic_service_reply(0, 15)
    def getDeviceMatchingData_reply(self, data):
        self.log("< getDeviceMatchingData")
        chexdump(data, print_fn=self.log)

class DPDevService(EPICEp):
    NAME = "dpdev"
    SERVICES = [
        DCPDPDeviceEpicTracer
    ]

class DPAVService(EPICEp):
    NAME = "dpavserv"

class DCPAVAudioInterfaceEpicTracer(EPICServiceTracer):
    NAME = "dcpav-audio-interface-epic"

    # usually 4, 6 but apparently also 0, 6 here?
    # or maybe a different open?
    @epic_service_cmd(0, 6)
    def open2(self, data):
        self.log("> open")
    @epic_service_reply(0, 6)
    def open2_reply(self, data):
        self.log("< open")
        chexdump(data, print_fn=self.log)

    @epic_service_cmd(0, 8)
    def prepareLink(self, data):
        self.log("> prepareLink")
    @epic_service_reply(0, 8)
    def prepareLink_reply(self, data):
        self.log("< prepareLink")
        chexdump(data, print_fn=self.log)

    @epic_service_cmd(0, 9)
    def startLink(self, data):
        self.log("> startLink")
    @epic_service_reply(0, 9)
    def startLink_reply(self, data):
        self.log("< startLink")
        chexdump(data, print_fn=self.log)

    @epic_service_cmd(0, 15)
    def getLinkStatus(self, data):
        self.log("> getLinkStatus")
    @epic_service_reply(0, 15)
    def getLinkStatus_reply(self, data):
        self.log("< getLinkStatus")
        chexdump(data, print_fn=self.log)

    @epic_service_cmd(0, 16)
    def getTransport(self, data):
        self.log("> getTransport")
    @epic_service_reply(0, 16)
    def getTransport_reply(self, data):
        self.log("< getTransport")
        chexdump(data, print_fn=self.log)

    @epic_service_cmd(0, 17)
    def getPortID(self, data):
        self.log("> getPortID")
    @epic_service_reply(0, 17)
    def getPortID_reply(self, data):
        self.log("< getPortID")
        chexdump(data, print_fn=self.log)

    @epic_service_cmd(1, 18)
    def getElements(self, data):
        self.log("> getElements")
    @epic_service_reply(1, 18)
    def getElements_reply(self, data):
        self.log("< getElements")
        chexdump(data, print_fn=self.log)

    @epic_service_cmd(1, 20)
    def getProductAttributes(self, data):
        self.log("> getProductAttributes")
    @epic_service_reply(1, 20)
    def getProductAttributes_reply(self, data):
        self.log("< getProductAttributes")
        chexdump(data, print_fn=self.log)

    @epic_service_cmd(1, 21)
    def getEDIDUUID(self, data):
        self.log("> getEDIDUUID")
    @epic_service_reply(1, 21)
    def getEDIDUUID_reply(self, data):
        self.log("< getEDIDUUID")
        chexdump(data, print_fn=self.log)

    @epic_service_cmd(0, 22)
    def getDataLatency(self, data):
        self.log("> getDataLatency")
    @epic_service_reply(0, 22)
    def getDataLatency_reply(self, data):
        self.log("< getDataLatency")
        chexdump(data, print_fn=self.log)


class AVService(EPICEp):
    NAME = "av"
    SERVICES = [
        DCPAVAudioInterfaceEpicTracer
    ]

class DCPDPTXHDCPAuthSessionTracer(EPICServiceTracer):
    NAME = "dcpdptx-hdcp-auth-session"

    @epic_service_cmd(4, 8)
    def getProtocol(self, data):
        self.log("> getProtocol")
    @epic_service_reply(4, 8)
    def getProtocol_reply(self, data):
        self.log("< getProtocol")
        chexdump(data, print_fn=self.log)

class HDCPService(EPICEp):
    NAME = "hdcp"
    SERVICES = [
        DCPDPTXHDCPAuthSessionTracer
    ]

class RemoteAllocService(EPICEp):
    NAME = "remotealloc"

class DCPDPTXRemotePortTarget(Register32):
    CORE = 3, 0
    ATC = 7, 4
    DIE = 11, 8
    CONNECTED = 15, 15

class DCPDPTXPortEpicTracer(EPICServiceTracer):
    NAME = "dcpdptx-port-epic"

    @epic_service_cmd(0, 8)
    def setPowerState(self, data):
        self.log("> setPowerState")
    @epic_service_reply(0, 8)
    def setPowerState_reply(self, data):
        self.log("< setPowerState")

    @epic_service_cmd(0, 13)
    def connectTo(self, data):
        unk1, target = struct.unpack("<II24x", data)
        target = DCPDPTXRemotePortTarget(target)
        self.log(f"> connectTo(target={target}, unk1=0x{unk1:x})")
    @epic_service_reply(0, 13)
    def connectTo_reply(self, data):
        unk1, target = struct.unpack("<II24x", data)
        target = DCPDPTXRemotePortTarget(target)
        self.log(f"< connectTo(target={target}, unk1=0x{unk1:x})")

    @epic_service_cmd(0, 14)
    def validateConnection(self, data):
        unk1, target = struct.unpack("<II40x", data)
        target = DCPDPTXRemotePortTarget(target)
        self.log(f"> validateConnection(target={target}, unk1=0x{unk1:x})")
    @epic_service_reply(0, 14)
    def validateConnection_reply(self, data):
        unk1, target = struct.unpack("<II40x", data)
        target = DCPDPTXRemotePortTarget(target)
        self.log(f"< validateConnection(target={target}, unk1=0x{unk1:x})")

    @epic_service_cmd(8, 10)
    def hotPlugDetectChangeOccurred(self, data):
        unk = struct.unpack("<16x?15x", data)[0]
        self.log(f"> hotPlugDetectChangeOccurred(unk={unk})")
    @epic_service_reply(8, 10)
    def hotPlugDetectChangeOccurred_reply(self, data):
        unk = struct.unpack("<16x?15x", data)[0]
        self.log(f"< hotPlugDetectChangeOccurred(unk={unk})")

class DPTXPortService(EPICEp):
    NAME = "dptxport"
    SERVICES = [
        DCPDPTXPortEpicTracer
    ]

class DCPTracer(ASCTracer):
    ENDPOINTS = {
        0x20: SystemService,
        0x21: TestService,
        0x22: DCPExpertService,
        0x23: Disp0Service,
        0x24: DPAVController,
        0x25: EPICEp, # dcpav-power-ep
        0x26: DPSACService,
        0x27: DPDevService,
        0x28: DPAVService,
        0x29: AVService,
        0x2a: DPTXPortService, # dcpdptx-port-ep
        0x2b: HDCPService,
        0x2c: EPICEp, # cb-ap-to-dcp-service-ep
        0x2d: RemoteAllocService,
        0x37: DCPEp, # iomfb-link
    }

    def handle_msg(self, direction, r0, r1):
        super().handle_msg(direction, r0, r1)
        #iomon.poll()



dart_dcp_tracer = DARTTracer(hv, dcp_dart_adt_path)
dart_dcp_tracer.start()

dart_disp0_tracer = DARTTracer(hv, disp0_dart_adt_path)
dart_disp0_tracer.start()

def readmem_iova(addr, size, readfn):
    try:
        return dart_dcp_tracer.dart.ioread(0, addr, size)
    except Exception as e:
        print(e)
        return None

iomon.readmem = readmem_iova

dcp_tracer = DCPTracer(hv, dcp_adt_path, verbose=1)
dcp_tracer.start(dart_dcp_tracer.dart)

#dcp_tracer.ep.dcpep.state.dumpfile = open("dcp.log", "a")
