import werkzeug.security
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm
from flask_gravatar import Gravatar
from forms import RegisterForm,LoginForm, CommentForm
from functools import wraps
import os

app = Flask(__name__)
# app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
app.config['SECRET_KEY'] = os.environ.get("APP_SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

#CONNECT TO DB
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

gravatar = Gravatar(app=app,
                    size = 100,
                    rating = 'x',
                    force_default = False,
                    force_lower = False,
                    use_ssl = False,
                    base_url=None
                    )

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

    # This will act like a List of BlogPost objects attached to each User.
    # This is a session created to connect the Blog posts related to the current person in the other table.
    posts = relationship('BlogPost', back_populates='author')

    # User > Comment
    comments = relationship("Comment", back_populates = "comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    #Create a relatioship between author and User, usres is the table holding the users's data in User
    author = relationship('User', back_populates="posts")
    #Here we create a ForeighKey , to relate the author to the usres table
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    # BlogPost > Comment
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key = True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    text = db.Column (db.String(250), nullable = False)
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))

    # Comment > BlogPost
    parent_post = relationship('BlogPost', back_populates= "comments")

    # Comment > Users
    comment_author = relationship("User", back_populates="comments")
# db.create_all()

# Admin only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args,**kwargs):
        #if the current user's id is not 1 then raises 403 error
        if not current_user.is_authenticated or current_user.id != 1:
            return abort(403)
        #Otherwise continue with the route function
        return f(*args,**kwargs)
    return decorated_function


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    if current_user.is_authenticated:
        #we use this boolean to send it to header page so  that it change its behaviour baed on the boolean
        is_logged_in = True
        #we need the users id to send to the index page so that we chose what content to show based on usser id, number
        # 1 is the admin, so the user number one sees every content

        return render_template("index.html", all_posts=posts, user_state = is_logged_in, user_index = current_user.id)
    else:
        is_logged_in = False
        return render_template("index.html", all_posts=posts, user_state = is_logged_in)


@app.route('/register', methods=["GET","POST"])
def register():
    form = RegisterForm()
    all_users = User.query.all()
    if request.method == "POST":
        if form.validate_on_submit():
            email = request.form.get("email")
            password = request.form.get("password")
            user = request.form.get("username")
            for typed_email in all_users:
                if typed_email.email == email:
                    flash("This account id already Exists.")
                    return redirect(url_for("login"))
            new_user = User(email= email,
                            password = werkzeug.security.generate_password_hash(password),
                            user = user)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET","POST"])
def login():
    form = LoginForm()
    if request.method == "POST":
        if form.validate_on_submit():
            email = request.form.get('email')
            password = request.form.get('password')

            all_users = User.query.all()
            for item in all_users:
                if item.email == email:
                    user = User.query.filter_by(email=email).first()
                    if check_password_hash(user.password,password=password):
                        login_user(user)
                        return redirect(url_for('get_all_posts'))
                    else:
                        flash("The user or the password might be wrong")
                else:
                    flash("This email is not exist!")
    return render_template("login.html", form= form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET","POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    # calling all the comment into an object called comment
    comments = Comment.query.all()
    related_comments = []
    # going through all the cooments,find any comment's post id that is same as the comment to be added to the database
    for comment in comments:
        if comment.post_id == post_id:
            related_comments.append(comment)
    # calling the user table to find the author of the specific comment
    user = User.query.all()

    form = CommentForm()
    # receiving comment from the comment section if, form conditions are applied and the user is validated
    if request.method == "POST":
        if form.validate_on_submit():
            if current_user.is_authenticated:
                new_comment =Comment(
                   author_id = current_user.id,
                   post_id = post_id,
                   text = request.form.get('comment')
                )
                db.session.add(new_comment)
                db.session.commit()
            else:
                flash("Sorry, but you are not logged in!")
                return redirect(url_for('login'))


    return render_template("post.html",users=user, comments = related_comments, post=requested_post, user_index = post_id, form = form)



@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>")
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    # app.run(host='0.0.0.0', port=5000)
    app.run(debug=True)
