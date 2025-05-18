from flask import Flask

app = Flask(__name__)

@app.route('/', methods=['GET'])
def hello_world():
    return "Hola Mundo"

@app.route('/users', methods=['GET'])
def get_users():
    return "Users endpoint"

@app.route('/test', methods=['GET'])
def get_test():
    return "Test endpoint"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
