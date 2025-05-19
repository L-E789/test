"""Flask app para autenticación básica, subida, listado y reproducción de videos."""
import os
import mimetypes
from flask import Flask, request, render_template, redirect, url_for, send_from_directory, session

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

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Gestionar la subida de uno o varios videos vía GET y POST."""
    if not session.get('logged_in'):               # proteger ruta
        return redirect(url_for('login'))
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        files = request.files.getlist('file')
        for file in files:
            if file and allowed_file(file.filename):
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
        return redirect(url_for('list_videos'))
    return render_template('upload.html')

@app.route('/videos', methods=['GET'])
def list_videos():
    """Mostrar la lista de videos subidos con metadatos."""
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    videos = []
    for f in files:
        path = os.path.join(app.config['UPLOAD_FOLDER'], f)
        size = os.path.getsize(path)
        size_mb = f"{size/(1024*1024):.2f} MB"
        # obtener duración solo si MoviePy está instalado
        if HAVE_MOVIEPY:
            try:
                clip = VideoFileClip(path)
                dur = clip.duration
                clip.reader.close(); clip.audio.reader.close_proc()
                h, r = divmod(dur, 3600)
                m, s = divmod(r, 60)
                duration_str = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
            except:
                duration_str = "n/a"
        else:
            duration_str = "n/a"
        videos.append({'name': f, 'size': size_mb, 'duration': duration_str})
    return render_template('list.html', videos=videos)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Servir un archivo de video desde la carpeta de uploads con MIME correcto."""
    response = send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    # for .mkv force the correct Content-Type
    if filename.lower().endswith('.mkv'):
        response.headers['Content-Type'] = 'video/x-matroska'
    return response

@app.route('/videos/<filename>', methods=['GET'])
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

@app.route('/admin', methods=['GET'])
def admin_panel():
    """Mostrar panel administrativo con paginación y búsqueda."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    # Obtener parámetros
    search = request.args.get('search', '').lower()
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    per_page = 5
    # Listar y filtrar
    all_videos = os.listdir(app.config['UPLOAD_FOLDER'])
    filtered = [v for v in all_videos if search in v.lower()]
    total = len(filtered)
    total_pages = (total + per_page - 1) // per_page
    # Slice para la página actual
    start = (page - 1) * per_page
    videos = filtered[start:start + per_page]
    return render_template(
        'admin.html',
        videos=videos,
        page=page,
        total_pages=total_pages,
        search=search
    )

@app.route('/admin/rename', methods=['POST'])
def admin_rename():
    """Renombrar un video existente."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    old = request.form['old_name']
    new = request.form['new_name']
    src = os.path.join(app.config['UPLOAD_FOLDER'], old)
    dst = os.path.join(app.config['UPLOAD_FOLDER'], new)
    if os.path.exists(src) and not os.path.exists(dst):
        os.rename(src, dst)
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete', methods=['POST'])
def admin_delete():
    """Eliminar un video existente."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    fname = request.form['del_name']
    path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for('admin_panel'))

@app.route('/', methods=['GET'])
def home():
    """Redirigir a la lista de videos."""
    return redirect(url_for('list_videos'))

if __name__ == '__main__':
    """Punto de entrada de la aplicación."""
    app.run(host='0.0.0.0', port=5000, debug=True)
