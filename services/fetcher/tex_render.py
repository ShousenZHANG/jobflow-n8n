import os, re, base64, shutil, subprocess, datetime
from typing import Dict, Any, Tuple
from jinja2 import Environment, FileSystemLoader, StrictUndefined

LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "#": r"\#",
    "$": r"\$",
    "%": r"\%",
    "&": r"\&",
    "_": r"\_",
    "^": r"\^{}",
    "~": r"\textasciitilde{}",
}

def latex_escape(value):
    if isinstance(value, dict):
        if value.get("__raw__") and "text" in value:
            return value["text"]
        return {k: latex_escape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [latex_escape(v) for v in value]
    if isinstance(value, str):
        out = value
        for ch, repl in LATEX_SPECIALS.items():
            out = out.replace(ch, repl)
        return out
    return value


def render_tex(template_dir: str, template_name: str, context: Dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(template_dir),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_name)
    safe_context = latex_escape(context)
    return template.render(**safe_context)

ENGINES = (
    ("tectonic", ["tectonic", "-X", "compile", "main.tex"]),
    ("latexmk", ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "main.tex"]),
    ("xelatex", ["xelatex", "-interaction=nonstopmode", "main.tex"]),
)

def pick_engine() -> Tuple[str, list] | None:
    for name, cmd in ENGINES:
        if shutil.which(name):
            return name, cmd
    return None


def write_and_compile(tex_content: str, out_root: str, filename: str | None = None, do_compile: bool = True):
    os.makedirs(out_root, exist_ok=True)
    if not filename:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"doc_{ts}"
    work_dir = os.path.join(out_root, filename)
    os.makedirs(work_dir, exist_ok=True)

    tex_path = os.path.join(work_dir, "main.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)

    pdf_path = os.path.join(work_dir, "main.pdf")
    log_path = os.path.join(work_dir, "build.log")

    engine = None
    rc = None
    if do_compile:
        picked = pick_engine()
        if picked:
            engine, cmd = picked
            try:
                proc = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True)
                rc = proc.returncode
                with open(log_path, "w", encoding="utf-8", errors="ignore") as lg:
                    lg.write(proc.stdout)
                    lg.write("\n--- STDERR ---\n")
                    lg.write(proc.stderr)
            except Exception as e:
                rc = -1
                with open(log_path, "w", encoding="utf-8", errors="ignore") as lg:
                    lg.write(f"Compile failed: {e}")
        else:
            rc = -2
    return {
        "work_dir": work_dir,
        "tex_path": tex_path,
        "pdf_path": pdf_path if os.path.isfile(pdf_path) else None,
        "log_path": log_path if os.path.isfile(log_path) else None,
        "engine": engine,
        "return_code": rc,
    }


def read_file_base64(path: str) -> str | None:
    if not path or not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

