"""Đọc model SAP2000 qua OAPI (COM) — CHỈ CHẠY TRÊN WINDOWS CÓ SAP2000.

`comtypes` CHỈ được import bên trong hàm, không import ở top-level, để
các module khác vẫn import/test được trên Linux.

ProgID ổn định qua các đời SAPFIRE: "CSI.SAP2000.API.SapObject",
helper "SAP2000v1.Helper" — KHÔNG hardcode version SAP.

Tên hàm/signature dưới đây theo CSI OAPI Documentation (file .chm trong
thư mục cài SAP) và ví dụ chính thức của CSI — CHƯA XÁC MINH bằng CHM
đúng version SAP2000 của user; lần chạy đầu trên máy thật là bước kiểm
chứng (xem HUONG_DAN_TEST.md). Mọi hàm COM trả int ret: ret != 0 sẽ
raise SapError với thông báo tiếng Việt rõ ràng.
"""

from __future__ import annotations

from .model import Joint, Reaction, SapOutput

# eLoadCaseType (SAP2000 v26/v27 — đối chiếu CHM đúng version trước khi dùng).
LOAD_CASE_TYPES = {
    1: "Linear Static",
    2: "Nonlinear Static",
    3: "Modal",
    4: "Response Spectrum",
    5: "Linear History",
    6: "Nonlinear History",
    7: "Linear Dynamic",
    8: "Nonlinear Dynamic",
    9: "Moving Load",
    10: "Buckling",
    11: "Steady State",
    12: "Power Spectral Density",
    13: "Linear Static MultiStep",
    14: "HyperStatic",
    15: "External Results",
    16: "Staged Construction",
    17: "Nonlinear Static MultiStep",
}
NONLINEAR_CASE_TYPES = {2, 6, 8, 16, 17}
MULTISTEP_ENVELOPE_TYPES = {4, 5, 7, 9, 11, 12, 13}

# eItemTypeElm: ObjectElm = 1 (joint object, khớp với PointObj).
ITEM_OBJECT_ELM = 1


class SapError(RuntimeError):
    pass


def _check(ret: int, action: str) -> None:
    if ret != 0:
        raise SapError(f"{action} thất bại (mã lỗi SAP trả về: {ret}).")


def _tolist(values) -> list:
    try:
        return list(values)
    except TypeError:
        return [values]


class SapConnection:
    """Kết nối tới SAP2000 đang mở, hoặc mở file .sdb mới."""

    def __init__(self, path: str | None = None):
        self.path = path
        self.sap_object = None
        self.model = None
        self._started_by_us = False

    # -- kết nối ---------------------------------------------------------
    def attach_or_open(self) -> None:
        try:
            import comtypes.client
        except ImportError as e:  # pragma: no cover - chỉ xảy ra ngoài Windows
            raise SapError(
                "Không tải được comtypes — app chỉ kết nối SAP trên Windows. "
                "Trên máy này hãy dùng chế độ Excel offline."
            ) from e
        helper = comtypes.client.CreateObject("SAP2000v1.Helper")
        helper = helper.QueryInterface(comtypes.gen.SAP2000v1.cHelper)
        if self.path:
            self.sap_object = helper.CreateObjectProgID("CSI.SAP2000.API.SapObject")
            self.sap_object.ApplicationStart()
            self._started_by_us = True
            self.model = self.sap_object.SapModel
            _check(self.model.File.OpenFile(self.path), f"Mở file {self.path}")
        else:
            try:
                self.sap_object = helper.GetObject("CSI.SAP2000.API.SapObject")
            except Exception:
                self.sap_object = helper.CreateObjectProgID("CSI.SAP2000.API.SapObject")
                self.sap_object.ApplicationStart()
                self._started_by_us = True
            self.model = self.sap_object.SapModel

    def close(self) -> None:
        if self.sap_object is not None and self._started_by_us:
            try:
                self.sap_object.ApplicationExit(False)
            except Exception:
                pass
        self.sap_object = None
        self.model = None

    def _need_model(self):
        if self.model is None:
            raise SapError("Chưa kết nối SAP2000 — bấm 'Kết nối SAP đang mở' trước.")
        return self.model

    # -- đơn vị / danh sách ---------------------------------------------
    def get_units(self) -> tuple[int, int]:
        """Trả về (mã đơn vị lực eForce, mã đơn vị dài eLength)."""
        model = self._need_model()
        ret, force, length, _temp = model.GetPresentUnits(0, 0, 0)
        _check(ret, "Đọc đơn vị hiện tại của model")
        return int(force), int(length)

    def list_load_patterns(self) -> list[str]:
        model = self._need_model()
        ret, n, names = model.LoadPattern.GetNameList(0, [])
        _check(ret, "Đọc danh sách load pattern")
        return _tolist(names)[: int(n)]

    # eLoadPatternType (đối chiếu CHM đúng version): Dead=1, SuperDead=2,
    # Live=3, Quake=5, Wind=6, Snow=7, Other=8.
    _PATTERN_TYPE_MAP = {
        1: "Dead", 2: "Super Dead", 3: "Live", 5: "Quake", 6: "Wind",
        7: "Other", 8: "Other", 10: "Other",
    }

    def get_pattern_info(self, name: str) -> dict:
        """{design_type, self_wt_mult} của 1 pattern (để map sang SAFE).

        GetSelfWtMult chưa xác minh tên hàm bằng CHM — nếu COM không có
        hàm này thì mặc định SelfWtMult=0 và ghi chú trong log của app.
        """
        model = self._need_model()
        design_type = ""
        try:
            ret, ptype = model.LoadPattern.GetType(name, 0)
            if ret == 0:
                design_type = self._PATTERN_TYPE_MAP.get(int(ptype), "Other")
        except Exception:
            pass
        self_wt_mult = 0.0
        try:
            ret, sw = model.LoadPattern.GetSelfWtMult(name, 0.0)
            if ret == 0:
                self_wt_mult = float(sw)
        except Exception:
            pass
        return {"design_type": design_type, "self_wt_mult": self_wt_mult}

    def list_load_cases(self) -> list[SapOutput]:
        model = self._need_model()
        ret, n, names = model.LoadCases.GetNameList(0, [])
        _check(ret, "Đọc danh sách load case")
        outputs: list[SapOutput] = []
        for name in _tolist(names)[: int(n)]:
            ret, ctype = model.LoadCases.GetType(name, 0)
            _check(ret, f"Đọc loại load case {name}")
            ctype = int(ctype)
            outputs.append(
                SapOutput(
                    name=name,
                    kind="case",
                    case_type=ctype,
                    is_nonlinear=ctype in NONLINEAR_CASE_TYPES,
                )
            )
        return outputs

    def list_combos(self) -> list[SapOutput]:
        model = self._need_model()
        ret, n, names = model.RespCombo.GetNameList(0, [])
        _check(ret, "Đọc danh sách load combo")
        outputs: list[SapOutput] = []
        for name in _tolist(names)[: int(n)]:
            ret, ctype = model.RespCombo.GetType(name, 0)
            _check(ret, f"Đọc loại combo {name}")
            ret, m, case_names, sfs = model.RespCombo.GetCaseList(name, 0, [], [])
            _check(ret, f"Đọc thành phần combo {name}")
            comps = list(zip(_tolist(case_names)[: int(m)], _tolist(sfs)[: int(m)]))
            outputs.append(
                SapOutput(
                    name=name,
                    kind="combo",
                    combo_type=str(ctype),
                    components=[(c, float(s)) for c, s in comps],
                )
            )
        return outputs

    # -- hình học --------------------------------------------------------
    def _all_points(self) -> list[tuple[str, float, float, float]]:
        model = self._need_model()
        ret, n, names = model.PointObj.GetNameList(0, [])
        _check(ret, "Đọc danh sách joint")
        points = []
        for name in _tolist(names)[: int(n)]:
            if name.startswith("~"):
                continue  # joint mesh nội bộ
            ret, x, y, z = model.PointObj.GetCoordCartesian(name, 0.0, 0.0, 0.0)
            _check(ret, f"Đọc tọa độ joint {name}")
            points.append((name, float(x), float(y), float(z)))
        return points

    def list_z_levels(self, tol: float = 0.005) -> list[float]:
        """Các cao độ Z có joint (gom nhóm theo tol), sắp xếp tăng dần."""
        levels: list[float] = []
        for _name, _x, _y, z in self._all_points():
            if not any(abs(z - lv) <= tol for lv in levels):
                levels.append(z)
        return sorted(levels)

    def get_joints_at_z(self, z: float, tol: float = 0.005) -> list[Joint]:
        model = self._need_model()
        joints: list[Joint] = []
        for name, x, y, pz in self._all_points():
            if abs(pz - z) > tol:
                continue
            ret, restraint = model.PointObj.GetRestraint(name, [False] * 6)
            restrained = False
            restraint_tuple = None
            if ret == 0:
                vals = [bool(v) for v in _tolist(restraint)][:6]
                if len(vals) == 6:
                    restraint_tuple = tuple(vals)  # type: ignore[assignment]
                    restrained = any(vals)
            joints.append(Joint(name=name, x=x, y=y, z=pz, restrained=restrained,
                                restraint=restraint_tuple))
        return joints

    def get_area_outlines_at_z(self, z: float, tol: float = 0.005) -> list[list[tuple[float, float]]]:
        """Outline các AreaObj có điểm tại Z (sàn tại level)."""
        model = self._need_model()
        ret, n, names = model.AreaObj.GetNameList(0, [])
        _check(ret, "Đọc danh sách area object")
        outlines: list[list[tuple[float, float]]] = []
        for name in _tolist(names)[: int(n)]:
            ret, m, points = model.AreaObj.GetPoints(name, 0, [])
            if ret != 0:
                continue
            coords = []
            for pt in _tolist(points)[: int(m)]:
                ret, x, y, pz = model.PointObj.GetCoordCartesian(pt, 0.0, 0.0, 0.0)
                if ret == 0:
                    coords.append((float(x), float(y), float(pz)))
            pts_at_z = [(x, y) for x, y, pz in coords if abs(pz - z) <= tol]
            if len(pts_at_z) >= 3:
                outlines.append(pts_at_z)
        return outlines

    # -- phản lực ---------------------------------------------------------
    def get_joint_reactions(
        self, outputs: list[SapOutput]
    ) -> list[Reaction]:
        """Đọc JointReact cho từng output đã chọn (case hoặc combo).

        Mỗi output được chọn riêng (DeselectAll + SetCase/ComboSelected)
        rồi mới đọc, để không lẫn kết quả các output khác.
        """
        model = self._need_model()
        reactions: list[Reaction] = []
        for out in outputs:
            _check(
                model.Results.Setup.DeselectAllCasesAndCombosForOutput(),
                "Bỏ chọn output trước khi đọc phản lực",
            )
            if out.kind == "combo":
                ret = model.Results.Setup.SetComboSelectedForOutput(out.name)
                _check(ret, f"Chọn combo {out.name} để đọc phản lực")
            else:
                ret = model.Results.Setup.SetCaseSelectedForOutput(out.name)
                _check(ret, f"Chọn case {out.name} để đọc phản lực")
            res = model.Results.JointReact(
                "", ITEM_OBJECT_ELM, 0, [], [], [], [], [], [], [], [], [], [], []
            )
            ret = res[0]
            _check(ret, f"Đọc phản lực của {out.name}")
            (_ret, n, _obj, _elm, acase, steptype, stepnum,
             f1, f2, f3, m1, m2, m3) = res
            n = int(n)
            for i in range(n):
                reactions.append(
                    Reaction(
                        joint=str(_tolist(_obj)[i]),
                        output_name=str(_tolist(acase)[i]),
                        output_kind=out.kind,
                        step_type=str(_tolist(steptype)[i]),
                        step_num=float(_tolist(stepnum)[i]),
                        f1=float(_tolist(f1)[i]),
                        f2=float(_tolist(f2)[i]),
                        f3=float(_tolist(f3)[i]),
                        m1=float(_tolist(m1)[i]),
                        m2=float(_tolist(m2)[i]),
                        m3=float(_tolist(m3)[i]),
                    )
                )
        return reactions
