# PPT rendering modes

Xiaopu separates structural verification from visual rendering.

- Windows desktop: PowerPoint COM export, when an interactive Office logon
  session is available.
- Linux benchmark: use `Dockerfile.ppt-render`, which installs LibreOffice
  Impress and CJK fonts. The container can then export slides to PNG/PDF for
  montage inspection.
- Headless structural-only mode: `ppt_verify` remains available when neither
  renderer exists.

A structurally valid deck must not be reported as visually verified. The pilot
result schema records the verification kind and the renderer failure separately.
