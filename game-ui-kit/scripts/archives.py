"""Read bounded artwork from ZIP/RAR without extracting paths or links."""
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import unicodedata
import zipfile

ARTWORK = {".png", ".jpg", ".jpeg", ".webp", ".psd"}
MAX_MEMBERS = 3000
MAX_BYTES = 1024 * 1024 * 1024


def safe_name(name):
    raw = name.replace("\\", "/")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or re.match(r"^[a-zA-Z]:", raw):
        raise ValueError(f"Đường dẫn không an toàn trong gói: {name}")
    return path


def part_name(name):
    name = unicodedata.normalize("NFD", name.replace("đ", "d").replace("Đ", "D"))
    name = "".join(c for c in name if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_") or "item"


def read_members(archive, out, kit, artwork_only):
    entries = [m for m in archive.infolist() if not m.is_dir()]
    entries = [m for m in entries if not any(p.startswith(".") or p == "__MACOSX"
                                            for p in safe_name(m.filename).parts)]
    members = [m for m in entries if safe_name(m.filename).suffix.lower() in ARTWORK]
    # A mixed reference archive can itself be a document attachment; keep legacy behavior.
    if artwork_only and len(members) != len(entries):
        return []
    if len(entries) > MAX_MEMBERS or sum(m.file_size for m in members) > MAX_BYTES:
        raise ValueError("Gói nén quá lớn: tối đa 3000 mục và 1 GB artwork sau giải nén.")
    files, used, total = [], {}, 0
    for member in members:
        link = getattr(member, "is_symlink", None)
        if (callable(link) and link()) or (getattr(member, "external_attr", 0) >> 16) & 0o170000 == 0o120000:
            raise ValueError("Gói artwork không nhận liên kết tượng trưng.")
        relative = safe_name(member.filename)
        with archive.open(member) as stream:
            content = stream.read(min(MAX_BYTES - total, member.file_size) + 1)
        if len(content) != member.file_size or total + len(content) > MAX_BYTES:
            raise ValueError("Kích thước giải nén không khớp hoặc vượt giới hạn.")
        total += len(content)
        parents = [part_name(p) for p in relative.parts[:-1]]
        stem = part_name(relative.stem)
        target = out.joinpath(*parents, stem + relative.suffix.lower())
        # Slug collisions must not silently drop another file or a screen state.
        if str(target).casefold() in used:
            suffix = hashlib.sha256(member.filename.encode()).hexdigest()[:10]
            target = target.with_name(stem + "_" + suffix + relative.suffix.lower())
        used[str(target).casefold()] = True
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        files.append({"path": target.relative_to(kit).as_posix(), "name": member.filename})
    if files and len(members) != len(entries):
        files[0]["archive_skipped"] = [m.filename for m in entries if m not in members]
    return files


def unpack(out, kit, data, *, kind="zip", artwork_only=False):
    if kind == "zip":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return read_members(archive, out, kit, artwork_only)
    try:
        import rarfile
    except ImportError as error:
        raise ValueError("Đọc RAR cần rarfile: chạy py -3 -m pip install rarfile; hoặc kéo folder đã giải nén.") from error
    # Windows ships libarchive as tar.exe; rarfile normally searches for 'bsdtar'.
    tar = shutil.which("bsdtar") or (shutil.which("tar") if __import__("os").name == "nt" else None)
    if tar:
        rarfile.BSDTAR_TOOL = tar
    unrar = shutil.which("unrar") or Path("C:/Program Files/WinRAR/UnRAR.exe")
    if Path(unrar).is_file():
        rarfile.UNRAR_TOOL = str(unrar)
    seven = shutil.which("7z") or Path("C:/Program Files/7-Zip/7z.exe")
    if Path(seven).is_file():
        rarfile.SEVENZIP_TOOL = str(seven)
    try:
        with tempfile.TemporaryDirectory(prefix="gui-rar-") as temporary:
            path = Path(temporary) / "input.rar"
            path.write_bytes(data)
            with rarfile.RarFile(path) as archive:
                if archive.needs_password():
                    raise ValueError("RAR có mật khẩu: giải nén trên máy rồi kéo folder vào form.")
                return read_members(archive, out, kit, artwork_only)
    except rarfile.Error as error:
        raise ValueError("Không giải nén được RAR. Cần 7-Zip/bsdtar hỗ trợ gói này, hoặc kéo folder đã giải nén. " + str(error)) from error
