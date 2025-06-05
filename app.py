"""Flask app para autenticación básica, subida, listado y reproducción de videos."""
import os
import mimetypes
from flask import Flask, request, render_template, redirect, url_for, send_from_directory, session, jsonify
from werkzeug.utils import secure_filename

# intentar usar MoviePy para obtener duración
try:
    from moviepy.editor import VideoFileClip
    HAVE_MOVIEPY = True
except ImportError:
    HAVE_MOVIEPY = False

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecreto'          # nueva clave para sesiones
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'mkv'}
app.config['USERNAME'] = 'admin'
app.config['PASSWORD'] = 'admin'

# ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
mimetypes.add_type('video/x-matroska', '.mkv')

def allowed_file(filename):
    """Comprobar si la extensión del archivo está permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def list_files_recursive(base_dir):
    result = []
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            rel_dir = os.path.relpath(root, base_dir)
            rel_file = os.path.join(rel_dir, f) if rel_dir != '.' else f
            result.append(rel_file)
    return result

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Gestionar la subida de uno o varios videos vía GET y POST, con selección de carpeta."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        folder = request.form.get('folder') or ''
        target_dir = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(folder))
        os.makedirs(target_dir, exist_ok=True)
        if 'file' not in request.files:
            return redirect(request.url)
        files = request.files.getlist('file')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(target_dir, filename))
        return redirect(url_for('list_videos'))
    # GET: list existing folders
    dirs = [d for d in os.listdir(app.config['UPLOAD_FOLDER']) if os.path.isdir(os.path.join(app.config['UPLOAD_FOLDER'], d))]
    return render_template('upload.html', dirs=dirs)

@app.route('/create_folder', methods=['POST'])
def create_folder():
    """Crear una nueva carpeta dentro de uploads."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    name = secure_filename(request.form.get('new_folder', ''))
    if name:
        path = os.path.join(app.config['UPLOAD_FOLDER'], name)
        os.makedirs(path, exist_ok=True)
    return redirect(url_for('upload_file'))

@app.route('/videos', defaults={'folder': ''})
@app.route('/videos/<path:folder>')
def list_videos(folder):
    """Mostrar la lista de videos y subcarpetas dentro de la carpeta indicada."""
    base = app.config['UPLOAD_FOLDER']
    current_dir = os.path.join(base, folder)
    # Listar carpetas y archivos
    dirs = []
    files = []
    if os.path.exists(current_dir):
        for entry in os.listdir(current_dir):
            full_path = os.path.join(current_dir, entry)
            rel_path = os.path.join(folder, entry) if folder else entry
            if os.path.isdir(full_path):
                dirs.append({'name': entry, 'rel': rel_path})
            elif allowed_file(entry):
                size = os.path.getsize(full_path)
                size_mb = f"{size/(1024*1024):.2f} MB"
                # obtener duración solo si MoviePy está instalado
                if HAVE_MOVIEPY:
                    try:
                        clip = VideoFileClip(full_path)
                        dur = clip.duration
                        clip.reader.close();
                        if clip.audio: clip.audio.reader.close_proc()
                        h, r = divmod(dur, 3600)
                        m, s = divmod(r, 60)
                        duration_str = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
                    except:
                        duration_str = "n/a"
                else:
                    duration_str = "n/a"
                files.append({'name': entry, 'rel': rel_path, 'size': size_mb, 'duration': duration_str})
    # Para navegación hacia atrás
    parent = os.path.dirname(folder) if folder else None
    return render_template('list.html', dirs=dirs, files=files, folder=folder, parent=parent)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Servir un archivo de video desde la carpeta de uploads con MIME correcto, incluyendo subcarpetas."""
    response = send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    if filename.lower().endswith('.mkv'):
        response.headers['Content-Type'] = 'video/x-matroska'
    return response

@app.route('/videos/<path:filename>', methods=['GET'])
def view_video(filename):
    """Renderizar el reproductor HTML5 para el video indicado."""
    return render_template('view.html', filename=filename)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Gestionar el inicio de sesión de usuario."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == app.config['USERNAME'] and password == app.config['PASSWORD']:
            session['logged_in'] = True
            return redirect(url_for('admin_panel'))    # <-- aquí
    return render_template('login.html')

@app.route('/admin', defaults={'folder': ''}, methods=['GET'])
@app.route('/admin/<path:folder>', methods=['GET'])
def admin_panel(folder):
    """Panel admin: filtrar por carpeta, mostrar subcarpetas y archivos, paginar archivos."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    search = request.args.get('search', '').lower()
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    per_page = 10
    base = app.config['UPLOAD_FOLDER']
    current_dir = os.path.join(base, folder)
    dirs = []
    files = []
    if os.path.exists(current_dir):
        for entry in os.listdir(current_dir):
            full_path = os.path.join(current_dir, entry)
            rel_path = os.path.join(folder, entry) if folder else entry
            if os.path.isdir(full_path):
                dirs.append({'name': entry, 'rel': rel_path})
            elif allowed_file(entry) and (search in entry.lower()):
                files.append({'name': entry, 'rel': rel_path})
    total = len(files)
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    files_page = files[start:start + per_page]
    parent = os.path.dirname(folder) if folder else None
    return render_template(
        'admin.html',
        dirs=dirs,
        files=files_page,
        folder=folder,
        parent=parent,
        page=page,
        total_pages=total_pages,
        search=search,
        total_files=total
    )

@app.route('/admin/rename', methods=['POST'])
def admin_rename():
    """Renombrar un video existente (soporta subcarpetas)."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    old = request.form['old_name']
    new = request.form['new_name']
    src = os.path.join(app.config['UPLOAD_FOLDER'], old)
    dst = os.path.join(app.config['UPLOAD_FOLDER'], new)
    dst_dir = os.path.dirname(dst)
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir, exist_ok=True)
    if os.path.exists(src) and not os.path.exists(dst):
        os.rename(src, dst)
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete', methods=['POST'])
def admin_delete():
    """Eliminar un video existente (soporta subcarpetas)."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    fname = request.form['del_name']
    path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_multi', methods=['POST'])
def admin_delete_multi():
    """Borrar varios archivos seleccionados o todos los de una carpeta."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    files = request.form.getlist('files')
    folder = request.form.get('folder', '')
    base = app.config['UPLOAD_FOLDER']
    if 'delete_all' in request.form:
        # Borrar todos los archivos de la carpeta
        current_dir = os.path.join(base, folder)
        for entry in os.listdir(current_dir):
            full_path = os.path.join(current_dir, entry)
            if os.path.isfile(full_path) and allowed_file(entry):
                os.remove(full_path)
    else:
        # Borrar solo los seleccionados
        for rel in files:
            path = os.path.join(base, rel)
            if os.path.exists(path):
                os.remove(path)
    return redirect(url_for('admin_panel', folder=folder))

@app.route('/admin/delete_folder', methods=['POST'])
def admin_delete_folder():
    """Borrar una carpeta y todo su contenido desde el panel admin."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    folder_name = request.form.get('folder_name', '')
    base = app.config['UPLOAD_FOLDER']
    abs_folder = os.path.join(base, folder_name)
    # Seguridad: no permitir borrar la raíz ni salir de uploads
    if abs_folder == base or not os.path.exists(abs_folder) or not os.path.isdir(abs_folder):
        return redirect(url_for('admin_panel'))
    import shutil
    shutil.rmtree(abs_folder)
    parent = os.path.dirname(folder_name)
    return redirect(url_for('admin_panel', folder=parent))

@app.route('/upload_chunk', methods=['POST'])
def upload_chunk():
    """Handle chunked video uploads into subfolders."""
    if not session.get('logged_in'):
        return jsonify({'error': 'unauthorized'}), 401
    folder = request.form.get('folder') or ''
    safe_folder = secure_filename(folder)
    target_dir = os.path.join(app.config['UPLOAD_FOLDER'], safe_folder)
    os.makedirs(target_dir, exist_ok=True)
    file = request.files.get('chunk')
    try:
        chunk_index = int(request.form['chunkIndex'])
        total_chunks = int(request.form['totalChunks'])
    except (KeyError, ValueError):
        return jsonify({'error': 'invalid chunk parameters'}), 400
    filename = request.form.get('fileName')
    if not file or not filename:
        return jsonify({'error': 'bad request'}), 400
    if not allowed_file(filename):
        return jsonify({'error': 'file type not allowed'}), 400
    temp_path = os.path.join(target_dir, filename + '.part')
    with open(temp_path, 'ab') as f:
        f.write(file.read())
    # If last chunk, finalize file
    if chunk_index == total_chunks - 1:
        final_path = os.path.join(target_dir, filename)
        os.rename(temp_path, final_path)
    return jsonify({'chunkIndex': chunk_index})

@app.route('/download/<path:filename>')
def download_file(filename):
    """Descargar archivo de video existente (soporta subcarpetas)."""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    return redirect(url_for('list_videos'))

@app.route('/', methods=['GET'])
def home():
    """Redirigir a la lista de videos."""
    return redirect(url_for('list_videos'))

if __name__ == '__main__':
    """Punto de entrada de la aplicación."""
    app.run(host='0.0.0.0', port=5000, debug=True)
