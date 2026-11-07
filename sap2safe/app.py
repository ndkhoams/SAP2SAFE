"""GUI Tkinter SAP2SAFE — tiếng Việt, 5 bước theo chiều dọc.

(1) Nguồn SAP: COM (SAP đang mở / file .sdb), file .$2k (offline, chỉ đọc
    định nghĩa), hoặc Excel Joint Reactions (offline).
(2) Chọn level Z (mặc định gợi ý Z của các joint có gối).
(3) Chọn output + step đóng băng.
(4) Tham số xuất (version SAFE, thư mục xuất).
(5) Preview + xuất .F2K + .sf (cùng nội dung) + .xlsx + .log.

File xuất CHỈ gồm points + restraints + loads (đúng như MONG.sf thật) —
không tự sinh slab/bbox. Mọi lỗi COM/đọc file hiện messagebox tiếng Việt.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .excel_reader import list_outputs, read_joint_reactions
from .excel_writer import write_safe_tables_xlsx
from .f2k_template import compare_with_writer
from .mapping import apply_sign_flip, build_name_map, decide_combo_mapping
from .model import F2kModel, Joint, SapOutput
from .report import write_log
from .s2k_reader import parse_s2k, s2k_outputs
from .sf_reader import so_sanh_voi_mong_sf
from .sf_writer import safe_pattern_type, write_f2k, write_sf
from .step_select import freeze_reactions
from .units import force_factor, length_factor, moment_factor


# ---------------------------------------------------------------- pipeline
def closure_outputs(outputs: list[SapOutput], selected: list[str]):
    """Mở rộng tập chọn: combo được chọn thì tự động gồm cả các thành phần
    của nó (case để đóng băng + combo lồng nhau), đệ quy."""
    by_name = {o.name: o for o in outputs}
    included: list[SapOutput] = []
    seen: set[str] = set()
    queue = list(selected)
    auto: list[str] = []
    while queue:
        name = queue.pop(0)
        if name in seen or name not in by_name:
            continue
        seen.add(name)
        out = by_name[name]
        included.append(out)
        if out.kind == "combo":
            for comp, _sf in out.components:
                if comp not in seen and comp in by_name:
                    queue.append(comp)
                    if comp not in selected:
                        auto.append(comp)
    return included, auto


def build_f2k_model(
    reactions,
    joints_xyz: dict[str, tuple[float, float, float]],
    outputs: list[SapOutput],
    selected: list[str],
    joints_restraint: dict[str, tuple[bool, bool, bool, bool, bool, bool]] | None = None,
    pattern_info: dict[str, dict] | None = None,
    step_mode: str = "last",
    specific: tuple[str, float] | None = None,
    flip_sign: bool = True,
    safe_version: str = "22.5.1",
):
    """Pipeline chung (GUI + test đều dùng được).

    Trả về (F2kModel, info_log, warnings). `reactions` phải ở đơn vị kN, m.
    Combo được COPY Y HỆT định nghĩa SAP (không đóng băng thành pattern
    riêng); các case thành phần được tự động đưa vào để đóng băng.
    """
    joints_restraint = joints_restraint or {}
    pattern_info = pattern_info or {}
    sel_outputs, auto = closure_outputs(outputs, selected)
    sel_names = {o.name for o in sel_outputs}
    outputs_by_name = {o.name: o for o in outputs}
    rows = [r for r in reactions if r.output_name in sel_names and r.output_kind == "case"]
    joints_xy = {n: (c[0], c[1]) for n, c in joints_xyz.items()}

    frozen, warnings = freeze_reactions(rows, step_mode, specific, joints_xy)
    if not frozen:
        raise ValueError("Không có phản lực nào sau khi đóng băng — kiểm tra "
                         "lại output đã chọn và joint tại level.")
    if auto:
        warnings.append(f"Tự động thêm thành phần của combo đã chọn: {', '.join(auto)}.")

    sap_sums: dict[str, float] = {}
    for ld in frozen:
        sap_sums[ld.pattern] = sap_sums.get(ld.pattern, 0.0) + ld.fz

    name_map = build_name_map(sel_outputs)

    def safe_pattern(pattern: str) -> str:
        for suffix in ("_MAX", "_MIN"):
            if pattern.endswith(suffix):
                return name_map.get(pattern[: -len(suffix)], pattern[: -len(suffix)]) + suffix
        return name_map.get(pattern, pattern)

    def base_of(pattern: str) -> str:
        for suffix in ("_MAX", "_MIN"):
            if pattern.endswith(suffix):
                return pattern[: -len(suffix)]
        return pattern

    flipped = apply_sign_flip(frozen, flip_sign)
    for ld in flipped:
        ld.pattern = safe_pattern(ld.pattern)
    sap_sums = {safe_pattern(k): v for k, v in sap_sums.items()}

    pattern_names: list[str] = []
    for ld in flipped:
        if ld.pattern not in pattern_names:
            pattern_names.append(ld.pattern)

    patterns = []
    for p in pattern_names:
        info_p = pattern_info.get(base_of(p), {})
        patterns.append({
            "name": p,
            "type": safe_pattern_type(info_p.get("design_type", "")) if info_p else "Other",
            "self_wt_mult": info_p.get("self_wt_mult", 0),
        })

    model = F2kModel(
        patterns=patterns,
        cases=[{"name": p, "type": "Linear Static"} for p in pattern_names],
        safe_version=safe_version,
    )
    sources: list[str] = []
    for out in sel_outputs:
        if out.kind != "combo":
            sources.append(f"{name_map[out.name]} <- case {out.name} (frozen, "
                           f"{'nonlinear' if out.is_nonlinear else 'linear'})")
            continue
        safe_name = name_map[out.name]
        mode, items, note = decide_combo_mapping(out, outputs_by_name)
        if mode == "rebuild":
            combo_items = [(name_map.get(c, c), sf) for c, sf in items]
        else:
            combo_items = [(safe_name, 1.0)]
        model.combos.append({"name": safe_name,
                             "type": out.combo_type or "Linear Add",
                             "items": combo_items})
        sources.append(f"{safe_name} <- combo {out.name} ({note})")
    for name in sorted(joints_xyz, key=lambda n: (0, int(n)) if n.lstrip("-").isdigit() else (1, n)):
        x, y, _z = joints_xyz[name]
        restraint = joints_restraint.get(name)
        if restraint is None:
            warnings.append(
                f"Joint {name}: không có thông tin gối — mặc định Yes cả 6 DOF.")
        model.points.append({"name": name, "x": x, "y": y, "restraint": restraint})
    for ld in flipped:
        model.point_loads.append({
            "point": ld.joint, "pattern": ld.pattern,
            "fx": ld.fx, "fy": ld.fy, "fz": ld.fz,
            "mx": ld.mx, "my": ld.my, "mz": ld.mz,
        })

    info = {
        "flip_sign": flip_sign,
        "name_map": name_map,
        "sources": sources,
        "loads": [{"pattern": ld.pattern, "fz": ld.fz} for ld in flipped],
        "sap_sums": sap_sums,
        "warnings": warnings,
        "safe_version": safe_version,
        "units": "kN, m, C",
        "notes": [],
    }
    return model, info, warnings


# ---------------------------------------------------------------- GUI
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"SAP2SAFE v{__version__} — SAP2000 -> SAFE (.F2K/.sf)")
        self.geometry("920x860")
        self.reactions = []
        self.joints3d: dict[str, tuple[float, float, float]] = {}
        self.joints_restraint: dict[str, tuple[bool, bool, bool, bool, bool, bool]] = {}
        self.pattern_info: dict[str, dict] = {}
        self.outputs: list[SapOutput] = []
        self.z_levels: list[float] = []
        self.joints_at_z: list[Joint] = []
        self.sap_conn = None
        self.s2k_model = None
        self.unit_factors = (1.0, 1.0)
        self.last_export_f2k: str | None = None
        self._build()

    def _build(self):
        pad = {"padx": 8, "pady": 4}
        f1 = ttk.LabelFrame(self, text="1. Nguồn SAP")
        f1.pack(fill="x", **pad)
        self.source_var = tk.StringVar(value="excel")
        ttk.Radiobutton(f1, text="SAP đang mở / file .sdb (COM, chỉ Windows)",
                        variable=self.source_var, value="com").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(f1, text="File .$2k (offline — chỉ đọc định nghĩa)",
                        variable=self.source_var, value="s2k").grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(f1, text="File Excel Joint Reactions (offline)",
                        variable=self.source_var, value="excel").grid(row=0, column=2, sticky="w")
        ttk.Button(f1, text="Kết nối SAP đang mở", command=self._connect_sap).grid(row=1, column=0, sticky="w")
        ttk.Button(f1, text="Mở file .sdb...", command=self._open_sdb).grid(row=1, column=1, sticky="w")
        ttk.Button(f1, text="Chọn file .$2k...", command=self._browse_s2k).grid(row=1, column=2, sticky="w")
        self.file_entry = ttk.Entry(f1, width=80)
        self.file_entry.grid(row=2, column=0, columnspan=2, sticky="ew")
        ttk.Button(f1, text="Chọn file Excel...", command=self._browse_excel).grid(row=2, column=2)
        ttk.Button(f1, text="Đọc model", command=self._read_model).grid(row=3, column=0, sticky="w")
        self.lbl_model = ttk.Label(f1, text="Chưa đọc model.")
        self.lbl_model.grid(row=3, column=1, columnspan=2, sticky="w")

        f2 = ttk.LabelFrame(self, text="2. Chọn level (cao độ Z)")
        f2.pack(fill="x", **pad)
        ttk.Label(f2, text="Z có joint:").grid(row=0, column=0, sticky="w")
        self.z_combo = ttk.Combobox(f2, width=18, state="readonly")
        self.z_combo.grid(row=0, column=1, sticky="w")
        ttk.Label(f2, text="hoặc nhập Z (m):").grid(row=0, column=2, sticky="w")
        self.z_entry = ttk.Entry(f2, width=12)
        self.z_entry.grid(row=0, column=3, sticky="w")
        ttk.Label(f2, text="tol (m):").grid(row=0, column=4, sticky="w")
        self.tol_entry = ttk.Entry(f2, width=8)
        self.tol_entry.insert(0, "0.005")
        self.tol_entry.grid(row=0, column=5, sticky="w")
        ttk.Button(f2, text="Liệt kê joint tại Z", command=self._list_joints).grid(row=0, column=6)
        self.lbl_joints = ttk.Label(f2, text="")
        self.lbl_joints.grid(row=1, column=0, columnspan=7, sticky="w")

        f3 = ttk.LabelFrame(self, text="3. Chọn output + step đóng băng")
        f3.pack(fill="x", **pad)
        ttk.Label(f3, text="Load Cases (chọn nhiều):").grid(row=0, column=0, sticky="w")
        ttk.Label(f3, text="Load Combos (chọn nhiều):").grid(row=0, column=1, sticky="w")
        self.lb_cases = tk.Listbox(f3, selectmode="multiple", height=8, width=38)
        self.lb_cases.grid(row=1, column=0, sticky="ew")
        self.lb_combos = tk.Listbox(f3, selectmode="multiple", height=8, width=38)
        self.lb_combos.grid(row=1, column=1, sticky="ew")
        self.step_var = tk.StringVar(value="last")
        for i, (val, txt) in enumerate([
            ("last", "Last step (mặc định)"),
            ("specific", "Step cụ thể"),
            ("governing", "Governing step (max |F3|)"),
            ("maxmin", "Tách MAX-MIN (chỉ Envelope/RS)"),
        ]):
            ttk.Radiobutton(f3, text=txt, variable=self.step_var, value=val).grid(
                row=2 + i, column=0, sticky="w")
        ttk.Label(f3, text="StepType:").grid(row=3, column=1, sticky="w")
        self.steptype_entry = ttk.Entry(f3, width=10)
        self.steptype_entry.insert(0, "Step")
        self.steptype_entry.grid(row=3, column=1, sticky="e")
        ttk.Label(f3, text="StepNum:").grid(row=4, column=1, sticky="w")
        self.stepnum_entry = ttk.Entry(f3, width=10)
        self.stepnum_entry.insert(0, "1")
        self.stepnum_entry.grid(row=4, column=1, sticky="e")
        self.flip_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f3, text="Đổi dấu phản lực -> tải SAFE (mặc định BẬT)",
                        variable=self.flip_var).grid(row=6, column=0, columnspan=2, sticky="w")

        f4 = ttk.LabelFrame(self, text="4. Tham số xuất")
        f4.pack(fill="x", **pad)
        ttk.Label(f4, text="SAFE version:").grid(row=0, column=0, sticky="w")
        self.version_entry = ttk.Entry(f4, width=10)
        self.version_entry.insert(0, "22.5.1")
        self.version_entry.grid(row=0, column=1, sticky="w")
        ttk.Label(f4, text="Thư mục xuất:").grid(row=0, column=2, sticky="w")
        self.outdir_entry = ttk.Entry(f4, width=45)
        self.outdir_entry.insert(0, os.getcwd())
        self.outdir_entry.grid(row=0, column=3, sticky="ew")
        ttk.Button(f4, text="Chọn...", command=self._browse_outdir).grid(row=0, column=4)
        ttk.Label(f4, text="File xuất chỉ gồm points + restraints + loads (như MONG.sf) — "
                           "không sinh sàn; import vào model SAFE đã có sẵn.",
                  foreground="gray").grid(row=1, column=0, columnspan=5, sticky="w")

        f5 = ttk.LabelFrame(self, text="5. Preview + xuất file")
        f5.pack(fill="both", expand=True, **pad)
        cols = ("Joint", "X", "Y", "Pattern", "FX", "FY", "FZ", "MX", "MY", "MZ")
        self.tree = ttk.Treeview(f5, columns=cols, show="headings", height=10)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=80 if c not in ("Joint", "Pattern") else 100)
        self.tree.pack(fill="both", expand=True)
        self.lbl_totals = ttk.Label(f5, text="")
        self.lbl_totals.pack(anchor="w")
        btns = ttk.Frame(f5)
        btns.pack(fill="x")
        ttk.Button(btns, text="Xem preview", command=self._preview).pack(side="left", padx=4)
        ttk.Button(btns, text="Xuất .F2K + .sf (+ .xlsx + .log)", command=self._export).pack(side="left", padx=4)
        ttk.Button(btns, text="So sánh với file SAFE mẫu...", command=self._validate).pack(side="left", padx=4)
        ttk.Button(btns, text="Kiểm bảng mẫu...", command=self._check_sample).pack(side="left", padx=4)

    def _err(self, title, msg):
        messagebox.showerror(title, msg)

    def _get_z_tol(self):
        try:
            tol = float(self.tol_entry.get())
        except ValueError:
            raise ValueError("tol phải là số (mặc định 0.005).")
        z_text = self.z_entry.get().strip()
        if z_text:
            try:
                z = float(z_text)
            except ValueError:
                raise ValueError("Z nhập tay phải là số.")
        elif self.z_combo.get():
            z = float(self.z_combo.get())
        else:
            raise ValueError("Chưa chọn cao độ Z (chọn trong combobox hoặc nhập tay).")
        return z, tol

    def _selected_outputs(self):
        names = [self.lb_cases.get(i) for i in self.lb_cases.curselection()]
        names += [self.lb_combos.get(i) for i in self.lb_combos.curselection()]
        return names

    def _build_model(self):
        selected = self._selected_outputs()
        if not selected:
            raise ValueError("Chưa chọn output nào (case hoặc combo).")
        z, tol = self._get_z_tol()
        if not self.joints_at_z:
            raise ValueError("Chưa liệt kê joint tại Z — bấm 'Liệt kê joint tại Z' trước.")
        joints_xyz = {j.name: (j.x, j.y, j.z) for j in self.joints_at_z}
        mode = self.step_var.get()
        specific = None
        if mode == "specific":
            try:
                specific = (self.steptype_entry.get().strip() or "Step",
                            float(self.stepnum_entry.get()))
            except ValueError:
                raise ValueError("StepNum phải là số.")
        model, info, warnings = build_f2k_model(
            self.reactions, joints_xyz, self.outputs, selected,
            joints_restraint=self.joints_restraint,
            pattern_info=self.pattern_info,
            step_mode=mode, specific=specific,
            flip_sign=self.flip_var.get(),
            safe_version=self.version_entry.get().strip() or "22.5.1",
        )
        info["z"] = z
        info["tol"] = tol
        info["counts"] = {"points": len(model.points), "patterns": len(model.patterns),
                          "cases": len(model.cases), "combos": len(model.combos)}
        return model, info, warnings

    def _connect_sap(self):
        try:
            from .sap_reader import SapConnection
            self.sap_conn = SapConnection()
            self.sap_conn.attach_or_open()
        except Exception as e:
            self._err("Không kết nối được SAP", str(e))
            return
        messagebox.showinfo("SAP2SAFE", "Đã kết nối SAP2000 đang mở.\nBấm 'Đọc model' để lấy danh sách case/combo.")

    def _open_sdb(self):
        path = filedialog.askopenfilename(title="Chọn file SAP2000 (.sdb)",
                                          filetypes=[("SAP2000", "*.sdb"), ("Tất cả", "*.*")])
        if not path:
            return
        try:
            from .sap_reader import SapConnection
            self.sap_conn = SapConnection(path)
            self.sap_conn.attach_or_open()
        except Exception as e:
            self._err("Không mở được file .sdb", str(e))
            return
        messagebox.showinfo("SAP2SAFE", f"Đã mở {path}.\nBấm 'Đọc model' để lấy danh sách case/combo.")

    def _browse_s2k(self):
        path = filedialog.askopenfilename(title="Chọn file SAP2000 text (.$2k)",
                                          filetypes=[("SAP2000 text", "*.$2k"), ("Tất cả", "*.*")])
        if path:
            self.source_var.set("s2k")
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, path)

    def _browse_excel(self):
        path = filedialog.askopenfilename(title="Chọn file Excel Joint Reactions",
                                          filetypes=[("Excel", "*.xlsx"), ("Tất cả", "*.*")])
        if path:
            self.source_var.set("excel")
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, path)

    def _browse_outdir(self):
        path = filedialog.askdirectory()
        if path:
            self.outdir_entry.delete(0, tk.END)
            self.outdir_entry.insert(0, path)

    def _read_model(self):
        try:
            mode = self.source_var.get()
            if mode == "com":
                self._read_model_com()
            elif mode == "s2k":
                self._read_model_s2k()
            else:
                self._read_model_excel()
        except Exception as e:
            self._err("Đọc model thất bại", str(e))
            return
        self.z_combo["values"] = [f"{z:.3f}" for z in self.z_levels]
        suggested = getattr(self, "_suggested_z", None)
        if self.z_levels:
            if suggested is not None and any(abs(suggested - z) <= 0.005 for z in self.z_levels):
                self.z_combo.set(f"{suggested:.3f}")
            else:
                self.z_combo.current(0)
        self.lb_cases.delete(0, tk.END)
        self.lb_combos.delete(0, tk.END)
        for o in self.outputs:
            (self.lb_cases if o.kind == "case" else self.lb_combos).insert(tk.END, o.name)
        self.lbl_model.config(
            text=f"Đã đọc: {len(self.outputs)} output, {len(self.joints3d)} joint, "
                 f"{len(self.z_levels)} cao độ Z.")

    def _read_model_excel(self):
        path = self.file_entry.get().strip()
        if not path or not os.path.exists(path):
            raise ValueError("Chưa chọn file Excel Joint Reactions (hoặc file không tồn tại).")
        reactions, joints = read_joint_reactions(path)
        self.reactions = reactions
        self.joints3d = joints
        self.joints_restraint = {}
        self.pattern_info = {}
        self.outputs = [SapOutput(name=n, kind="case") for n in list_outputs(reactions)]
        levels: list[float] = []
        for _n, (_x, _y, z) in joints.items():
            if not any(abs(z - lv) <= 0.005 for lv in levels):
                levels.append(z)
        self.z_levels = sorted(levels)
        self._suggested_z = None

    def _read_model_s2k(self):
        path = self.file_entry.get().strip()
        if not path or not os.path.exists(path):
            raise ValueError("Chưa chọn file .$2k (hoặc file không tồn tại).")
        model = parse_s2k(path)
        self.s2k_model = model
        self.outputs = s2k_outputs(model)
        self.joints3d = dict(model.joints)
        self.joints_restraint = dict(model.restraints)
        self.pattern_info = {p["name"]: {"design_type": p["design_type"],
                                         "self_wt_mult": p["self_wt_mult"]}
                             for p in model.patterns}
        self.z_levels = model.z_levels()
        self._suggested_z = model.suggested_z()
        self.reactions = []  # phản lực lấy sau qua COM hoặc Excel
        messagebox.showinfo(
            "SAP2SAFE",
            f"Đã đọc .$2k: {model.program} {model.version}, {len(model.patterns)} pattern, "
            f"{len(model.cases)} case, {len(model.combos)} combo.\n"
            f"Gợi ý Z = {self._suggested_z} (nhiều joint có gối nhất).\n"
            "Lưu ý: file .$2k không chứa phản lực — cần đọc phản lực qua COM "
            "hoặc file Excel Joint Reactions trước khi xuất.")

    def _read_model_com(self):
        if self.sap_conn is None or self.sap_conn.model is None:
            raise ValueError("Chưa kết nối SAP — bấm 'Kết nối SAP đang mở' hoặc 'Mở file .sdb...' trước.")
        f_code, l_code = self.sap_conn.get_units()
        ff, lf = force_factor(f_code), length_factor(l_code)
        mf = moment_factor(f_code, l_code)
        self.unit_factors = (ff, mf)
        self._com_units = (f_code, l_code)
        cases = self.sap_conn.list_load_cases()
        combos = self.sap_conn.list_combos()
        self.outputs = cases + combos
        self.z_levels = self.sap_conn.list_z_levels()
        self._suggested_z = None
        self.pattern_info = {}
        for name in self.sap_conn.list_load_patterns():
            self.pattern_info[name] = self.sap_conn.get_pattern_info(name)
        messagebox.showinfo("SAP2SAFE",
                            f"Đã đọc model SAP (đơn vị: lực mã {f_code}, dài mã {l_code}).\n"
                            "Chọn Z rồi bấm 'Liệt kê joint tại Z'.")

    def _list_joints(self):
        try:
            z, tol = self._get_z_tol()
            if self.source_var.get() == "com" and self.sap_conn is not None:
                self.joints_at_z = self.sap_conn.get_joints_at_z(z, tol)
                self.joints_restraint = {j.name: j.restraint for j in self.joints_at_z
                                         if j.restraint}
                ff, mf = self.unit_factors
                lf = length_factor(self._com_units[1])
                cases_only = [o for o in self.outputs if o.kind == "case"]
                reactions = self.sap_conn.get_joint_reactions(cases_only)
                for r in reactions:
                    r.f1 *= ff; r.f2 *= ff; r.f3 *= ff
                    r.m1 *= mf; r.m2 *= mf; r.m3 *= mf
                for j in self.joints_at_z:
                    j.x *= lf; j.y *= lf; j.z *= lf
                self.joints3d = {j.name: (j.x, j.y, j.z) for j in self.joints_at_z}
                self.reactions = reactions
            else:
                self.joints_at_z = [
                    Joint(name=n, x=x, y=y, z=zz,
                          restrained=n in self.joints_restraint,
                          restraint=self.joints_restraint.get(n))
                    for n, (x, y, zz) in self.joints3d.items() if abs(zz - z) <= tol
                ]
            n_restr = sum(1 for j in self.joints_at_z if j.restrained)
            self.lbl_joints.config(
                text=f"Z = {z:.3f} m: {len(self.joints_at_z)} joint "
                     f"(trong đó {n_restr} joint có gối).")
        except Exception as e:
            self._err("Liệt kê joint thất bại", str(e))

    def _preview(self):
        try:
            model, info, warnings = self._build_model()
        except Exception as e:
            self._err("Preview thất bại", str(e))
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        for ld in model.point_loads:
            pt = next((p for p in model.points if p["name"] == ld["point"]), None)
            self.tree.insert("", "end", values=(
                ld["point"], f"{pt['x']:.3f}" if pt else "", f"{pt['y']:.3f}" if pt else "",
                ld["pattern"], f"{ld['fx']:.1f}", f"{ld['fy']:.1f}", f"{ld['fz']:.1f}",
                f"{ld['mx']:.1f}", f"{ld['my']:.1f}", f"{ld['mz']:.1f}"))
        totals = {}
        for ld in model.point_loads:
            totals[ld["pattern"]] = totals.get(ld["pattern"], 0.0) + ld["fz"]
        self.lbl_totals.config(text="  |  ".join(
            f"ΣFZ {p} = {v:.1f} kN" for p, v in totals.items()))
        if warnings:
            messagebox.showwarning("Cảnh báo", "\n".join(warnings))

    def _export(self):
        try:
            model, info, warnings = self._build_model()
        except Exception as e:
            self._err("Xuất file thất bại", str(e))
            return
        outdir = self.outdir_entry.get().strip() or os.getcwd()
        os.makedirs(outdir, exist_ok=True)
        z = info["z"]
        base = os.path.join(outdir, f"SAP2SAFE_Z{z:.2f}")
        try:
            counts = write_f2k(base + ".f2k", model)
            write_sf(base + ".sf", model)
            write_safe_tables_xlsx(base + ".xlsx", model)
            write_log(base + ".log", info)
        except Exception as e:
            self._err("Ghi file thất bại", str(e))
            return
        self.last_export_f2k = base + ".f2k"
        msg = (f"Đã xuất:\n{base}.f2k\n{base}.sf (cùng nội dung)\n{base}.xlsx\n{base}.log\n\n"
               f"{counts['points']} point, {counts['patterns']} pattern, "
               f"{counts['cases']} case, {counts['combos']} combo.")
        if warnings:
            msg += "\n\nCảnh báo:\n" + "\n".join(warnings)
        messagebox.showinfo("Xuất xong", msg)

    def _validate(self):
        if not self.last_export_f2k:
            self._err("Chưa có file xuất", "Hãy bấm 'Xuất .F2K + .sf' trước, rồi mới so sánh.")
            return
        sample = filedialog.askopenfilename(
            title="Chọn file SAFE mẫu (.sf/.F2K, vd MONG.sf)",
            filetypes=[("SAFE text", "*.sf *.f2k"), ("Tất cả", "*.*")])
        if not sample:
            return
        try:
            report = so_sanh_voi_mong_sf(self.last_export_f2k, sample)
        except Exception as e:
            self._err("So sánh thất bại", str(e))
            return
        win = tk.Toplevel(self)
        win.title("So sánh với file SAFE mẫu")
        txt = tk.Text(win, width=100, height=35)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", report)

    def _check_sample(self):
        path = filedialog.askopenfilename(title="Chọn file .F2K/.sf mẫu",
                                          filetypes=[("SAFE text", "*.sf *.f2k"), ("Tất cả", "*.*")])
        if not path:
            return
        try:
            report = compare_with_writer(path)
        except Exception as e:
            self._err("Đọc file mẫu thất bại", str(e))
            return
        win = tk.Toplevel(self)
        win.title("So sánh bảng với file mẫu")
        txt = tk.Text(win, width=90, height=30)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", report)


def run():
    app = App()
    app.mainloop()
