from flask import Flask, render_template, request, url_for, redirect, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash,check_password_hash
import psycopg2
from datetime import datetime
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm as c
from keras.models import model_from_json
from keras import backend as K
import os, io
import pytz
# import gc

app = Flask(__name__)
app.secret_key = 'my_crop_yield'
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024
PEOPLE_FOLDER =os.path.join('static')
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])
app.config['UPLOAD_FOLDER'] = PEOPLE_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


class User:
    def __init__(self, username):
        self.username = username

    @staticmethod
    def is_authenticated():
        return True

    @staticmethod
    def is_active():
        return True

    @staticmethod
    def is_anonymous():
        return False

    def get_id(self):
        return self.username


@login_manager.user_loader
def load_user(username):
    return User(username)


@app.route('/')
def first():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    else:
        return redirect(url_for('login'))

    
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = str(request.form.get('emailid'))
        phone = request.form.get('phone')
        password = request.form.get('pass')
        confirm = request.form.get('conf_pass')
        conn = psycopg2.connect('postgres://vcgfznklwqbvwf:913359968a36ee943a216cec0d7d4a8d1f82f03c5b7af8b0cca43745b21c7943@ec2-54-225-173-42.compute-1.amazonaws.com:5432/d6k5j4k7j0vn8m')
        cur = conn.cursor()
        cur.execute('select * from user_mail')
        data = cur.fetchall()
        print(password,confirm)
        for x in data:            
            if password == confirm and x[0] == str(email):
                encrypt_pass = generate_password_hash(password)
                cur.execute("insert into acye_login(email,mobile_number,password) values ('%s','%s','%s')"%(email, phone, encrypt_pass))
                conn.commit()
                flash("Registration successfull.Signin")
                return redirect(url_for('login'))
        else:
            flash("Your credentials does not match,Try again")
            return redirect(url_for('signup'))
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password_input = request.form.get('password')
        conn = psycopg2.connect('postgres://vcgfznklwqbvwf:913359968a36ee943a216cec0d7d4a8d1f82f03c5b7af8b0cca43745b21c7943@ec2-54-225-173-42.compute-1.amazonaws.com:5432/d6k5j4k7j0vn8m')
        cur = conn.cursor()
        cur.execute('select * from acye_login')
        data1 = cur.fetchall()
        conn.commit()
        for y in data1:
            if y[0] == str(email) and check_password_hash(y[2], password_input):
                login_user(User(email), remember=True)
                return redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check EmailID and password', 'danger')
    return render_template('login.html')


@app.route("/logout/")
@login_required
def logout():   
    logout_user()
    try:
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'])
        test = os.listdir(folder_path)
        for images in test:
            if images.endswith(".png"):
                os.remove(os.path.join(folder_path, images))        
    except:
        pass
    return redirect(url_for('login'))


def load_model():
    # Function to load and return neural network model    
    json_file = open('Flask_api/models/Model.json', 'r')
    loaded_model_json = json_file.read()
    json_file.close()    
    loaded_model = model_from_json(loaded_model_json)
    loaded_model.load_weights("Flask_api/weights/model_A_weights.h5")
    return loaded_model


def create_img(path):
    # Function to load,normalize and return image    
    im = Image.open(path).convert('RGB')    
    im = np.array(im)
    im = im / 255.0  
    print(path)
    im[:, :, 0] = (im[:, :, 0] - 0.485) / 0.229
    im[:, :, 1] = (im[:, :, 1] - 0.456) / 0.224
    im[:, :, 2] = (im[:, :, 2] - 0.406) / 0.225    
    im = np.expand_dims(im, axis=0)
    return im


def predict(path):
    # Function to load image,predict heat map, generate count and return (count , image , heat map)    
    model = load_model()    
    image = create_img(path) 
    print("ML part execution started")    
    ans = model.predict_on_batch(image)
#     K.clear_session()
#     gc.collect()
    count = np.sum(ans)   
    return count, image, ans


@app.route('/index', methods=['GET', 'POST'])
def home(): 
    ans=0
    blurred=''
    thermal=''
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)  
        file = request.files['file']            
        if file.filename == '':
            return redirect(request.url) 
        if file and allowed_file(file.filename):
            try:
                folder_path = os.path.join(app.config['UPLOAD_FOLDER'])
                test = os.listdir(folder_path)
                for images in test:
                    if images.endswith(".png"):
                        os.remove(os.path.join(folder_path, images))                
            except:
                pass
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))  
        else:
            flash('Allowed image types are -> png, jpg, jpeg and image size < 1MB')
            return redirect(request.url)                
            
        ist = pytz.timezone('Asia/Kolkata')       
        K.clear_session()       
        ans, img, hmap = predict(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        print("function call executed")
        plt.switch_backend('agg')              #used to clear the plot when the next loop is uploaded
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))           
        t = datetime.now(ist).strftime("%Y-%m-%d %H-%M-%S")
                            
        fig = plt.figure()
        ax = fig.add_subplot()
        ax.tick_params(axis='x', colors='white')  # setting up X-axis tick color to white
        ax.tick_params(axis='y', colors='white')  # setting up Y-axis tick color to white
        ax.spines['left'].set_color('white')      # setting up Y-axis tick color to white
        ax.spines['bottom'].set_color('white')    # setting up X-axis tick color to white
        plt.imshow(img.reshape(img.shape[1], img.shape[2], img.shape[3]))
        plt.savefig('static/image1'+str(t)+'.png', facecolor='#1F2328')    # setting up background color when save figure 
        blurred = os.path.join(app.config['UPLOAD_FOLDER'], 'image1'+str(t)+'.png')  # open the image saved and assign variable to it, to pass to html              
            
        fig = plt.figure()
        ax = fig.add_subplot()
        ax.tick_params(axis='x', colors='white')
        ax.tick_params(axis='y', colors='white') 
        ax.spines['left'].set_color('white') 
        ax.spines['bottom'].set_color('white')
        plt.imshow(hmap.reshape(hmap.shape[1], hmap.shape[2]), cmap=c.jet)
        plt.savefig('static/image2'+str(t)+'.png', facecolor='#1F2328')    
        thermal = os.path.join(app.config['UPLOAD_FOLDER'], 'image2'+str(t)+'.png')
        print("analysis completed")
        #  return render_template('index.html', ans=int(ans), image1=blurred, image2=thermal)       
          
    return render_template('index.html', ans=int(ans), image1=blurred, image2=thermal)
       
    
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error_page.html'), 404

    
if __name__ == '__main__':
    app.run(debug=True)
