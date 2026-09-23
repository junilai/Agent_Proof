# Compilación de la tesis: latexmk ejecuta XeLaTeX y biber las veces necesarias.
$pdf_mode = 5;       # XeLaTeX: la plantilla usa la fuente Times New Roman del sistema
$out_dir = 'build';  # archivos generados fuera del código fuente (ignorados por git)
@default_files = ('main.tex');  # sin esto latexmk también compila privado.tex, que no es un documento
