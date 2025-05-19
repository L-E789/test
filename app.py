from flask import Flask, request, render_template, redirect, url_for
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'mkv'}
app.config['USERNAME'] = 'admin'
app.config['PASSWORD'] = 'admin'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/', methods=['GET'])
def hello_world():
    return "Hola Mundo"

@app.route('/users', methods=['GET'])
def get_users():
    return "Users endpoint"

@app.route('/test', methods=['GET'])
def get_test():
    return "Test endpoint"

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('list_videos'))
    return render_template('upload.html')

@app.route('/videos', methods=['GET'])
def list_videos():
    videos = os.listdir(app.config['UPLOAD_FOLDER'])
    return render_template('list.html', videos=videos)

@app.route('/videos/<filename>', methods=['GET'])
def view_video(filename):
    return redirect(url_for('static', filename=os.path.join('uploads', filename)))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == app.config['USERNAME'] and password == app.config['PASSWORD']:
            return redirect(url_for('upload_file'))
    return render_template('login.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
