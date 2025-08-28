from flask import Flask, render_template, request, redirect, session, flash, url_for
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "supersecreto123"
DB_NAME = "database.db"

# Carpeta donde se guardarán los avatares subidos
UPLOAD_FOLDER = "static/avatars/"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# 🔹 Función para inicializar y actualizar la base de datos
def init_db():
    db_exists = os.path.exists(DB_NAME)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password TEXT
        )
    """)
    

    # Verificar si existen las columnas 'bio' y 'avatar'
    cursor.execute("PRAGMA table_info(usuarios)")
    columns = [info[1] for info in cursor.fetchall()]
    if "bio" not in columns:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN bio TEXT DEFAULT ''")
    if "avatar" not in columns:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN avatar TEXT DEFAULT ''")

    # Posts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            titulo TEXT,
            contenido TEXT,
            fecha TEXT
        )
    """)
    cursor.execute("PRAGMA table_info(posts)")
    post_columns = [info[1] for info in cursor.fetchall()]
    if "etiquetas" not in post_columns:
        cursor.execute("ALTER TABLE posts ADD COLUMN etiquetas TEXT DEFAULT ''")

    # Comentarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comentarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            contenido TEXT,
            fecha TEXT,
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )
    """)

    # Likes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )
    """)

    conn.commit()
    conn.close()

    db_exists = os.path.exists(DB_NAME)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password TEXT,
            bio TEXT DEFAULT '',
            avatar TEXT DEFAULT ''
        )
    """)

    # Posts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            titulo TEXT,
            contenido TEXT,
            fecha TEXT
        )
    """)

    # Verificar si la columna etiquetas existe
    cursor.execute("PRAGMA table_info(posts)")
    columns = [info[1] for info in cursor.fetchall()]
    if "etiquetas" not in columns:
        cursor.execute("ALTER TABLE posts ADD COLUMN etiquetas TEXT DEFAULT ''")

    # Comentarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comentarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            contenido TEXT,
            fecha TEXT,
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )
    """)

    # Likes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (user_id) REFERENCES usuarios(id)
        )
    """)

    conn.commit()
    conn.close()

# Inicializar la base de datos
init_db()

@app.context_processor
def inject_user():
    user_data = None
    if "user_id" in session:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, bio, avatar FROM usuarios WHERE id=?", (session["user_id"],))
        user_data = cursor.fetchone()
        conn.close()
    return dict(current_user=user_data, current_year=datetime.utcnow().year)


# 🔹 Login / Registro
@app.route("/")
def home():
    return redirect("/login") if "user_id" not in session else redirect("/index")
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO usuarios (username,email,password) VALUES (?,?,?)",
                (username, email, password)
            )
            conn.commit()
            conn.close()
            flash("Registro exitoso, ahora inicia sesión", "success")
            return redirect("/login")
        except sqlite3.IntegrityError:
            flash("Usuario o email ya existe", "danger")
            return redirect("/register")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username=?", (username,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user[3], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            flash("Has iniciado sesión correctamente", "success")
            return redirect("/index")
        flash("Usuario o contraseña incorrectos", "danger")
        return redirect("/login")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Has cerrado sesión", "info")
    return redirect("/login")

@app.route("/index")
def index():
    if "user_id" not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect("/login")

    search = request.args.get("search", "")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    query = """
    SELECT posts.id, posts.titulo, posts.contenido, posts.fecha, usuarios.username,
           (SELECT COUNT(*) FROM likes WHERE post_id=posts.id) as likes_count,
           (SELECT COUNT(*) FROM comentarios WHERE post_id=posts.id) as comentarios_count
    FROM posts
    JOIN usuarios ON posts.user_id=usuarios.id
    """
    if search:
        query += " WHERE posts.titulo LIKE ? OR posts.contenido LIKE ?"
        cursor.execute(query + " ORDER BY posts.id DESC", (f"%{search}%", f"%{search}%"))
    else:
        cursor.execute(query + " ORDER BY posts.id DESC")

    posts = cursor.fetchall()
    conn.close()
    return render_template("index.html", usuario=session.get("username"), posts=posts, search=search, datetime=datetime)

    if "user_id" not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect("/login")
    
    search = request.args.get("search", "")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    query = """
SELECT posts.id, posts.titulo, posts.contenido, posts.fecha, usuarios.username,
       (SELECT COUNT(*) FROM likes WHERE post_id=posts.id) as likes_count,
       (SELECT COUNT(*) FROM comentarios WHERE post_id=posts.id) as comentarios_count
FROM posts
JOIN usuarios ON posts.user_id=usuarios.id
"""


    if search:
        query += " WHERE posts.titulo LIKE ? OR posts.contenido LIKE ?"
        cursor.execute(query + " ORDER BY posts.id DESC", (f"%{search}%", f"%{search}%"))
    else:
        cursor.execute(query + " ORDER BY posts.id DESC")
    
    posts = cursor.fetchall()
    conn.close()
    return render_template("index.html", posts=posts, search=search)


# 🔹 Crear post
@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    if "user_id" not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect("/login")
    if request.method == "POST":
        titulo = request.form["titulo"]
        contenido = request.form["contenido"]
        etiquetas = request.form.get("etiquetas", "")
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO posts (user_id,titulo,contenido,fecha,etiquetas) VALUES (?,?,?,?,?)",
            (session["user_id"], titulo, contenido, fecha, etiquetas)
        )
        conn.commit()
        conn.close()
        flash("Post creado con éxito", "success")
        return redirect("/index")
    return render_template("create_post.html")

# 🔹 Ver post individual + comentarios
@app.route("/view_post/<int:post_id>", methods=["GET", "POST"])
def view_post(post_id):
    if "user_id" not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect("/login")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Obtener post
    cursor.execute("""
        SELECT posts.id, posts.titulo, posts.contenido, posts.fecha, posts.etiquetas, usuarios.username,
        (SELECT COUNT(*) FROM likes WHERE post_id=posts.id) as likes_count
        FROM posts JOIN usuarios ON posts.user_id=usuarios.id
        WHERE posts.id=?
    """, (post_id,))
    post = cursor.fetchone()
    # Comentarios
    cursor.execute("""
        SELECT comentarios.id, comentarios.contenido, comentarios.fecha, usuarios.username, comentarios.user_id
        FROM comentarios JOIN usuarios ON comentarios.user_id=usuarios.id
        WHERE comentarios.post_id=?
        ORDER BY comentarios.id ASC
    """, (post_id,))
    comentarios = cursor.fetchall()
    # Verificar like del usuario actual
    cursor.execute("SELECT * FROM likes WHERE post_id=? AND user_id=?", (post_id, session["user_id"]))
    liked = cursor.fetchone() is not None
    conn.close()
    return render_template("view_post.html", post=post, comentarios=comentarios, liked=liked)

# 🔹 Añadir comentario
@app.route("/add_comment/<int:post_id>", methods=["POST"])
def add_comment(post_id):
    if "user_id" not in session:
        return redirect("/login")
    contenido = request.form["contenido"]
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO comentarios (post_id,user_id,contenido,fecha) VALUES (?,?,?,?)",
        (post_id, session["user_id"], contenido, fecha)
    )
    conn.commit()
    conn.close()
    flash("Comentario agregado", "success")
    return redirect(f"/view_post/{post_id}")

# 🔹 Dar like / quitar like
@app.route("/toggle_like/<int:post_id>")
def toggle_like(post_id):
    if "user_id" not in session:
        return redirect("/login")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM likes WHERE post_id=? AND user_id=?", (post_id, session["user_id"]))
    exists = cursor.fetchone()
    if exists:
        cursor.execute("DELETE FROM likes WHERE post_id=? AND user_id=?", (post_id, session["user_id"]))
    else:
        cursor.execute("INSERT INTO likes (post_id,user_id) VALUES (?,?)", (post_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(f"/view_post/{post_id}")

@app.route("/profile/<int:user_id>")
def profile(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Información del usuario (sin avatar)
    cursor.execute("SELECT id, username, email, bio FROM usuarios WHERE id=?", (user_id,))
    user = cursor.fetchone()

    # Posts del usuario con conteo de likes y comentarios
    cursor.execute("""
        SELECT p.id, p.titulo, p.fecha,
               (SELECT COUNT(*) FROM comentarios c WHERE c.post_id=p.id) AS comentarios_count,
               (SELECT COUNT(*) FROM likes l WHERE l.post_id=p.id) AS likes_count
        FROM posts p
        WHERE p.user_id=?
        ORDER BY p.fecha DESC
    """, (user_id,))
    posts = cursor.fetchall()

    conn.close()
    return render_template("profile.html", user=user, posts=posts)


@app.route("/post/<int:post_id>/edit", methods=["GET", "POST"])
def edit_post(post_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Obtener datos del post
    cursor.execute("SELECT titulo, contenido FROM posts WHERE id=?", (post_id,))
    post = cursor.fetchone()

    if request.method == "POST":
        titulo = request.form["titulo"]
        contenido = request.form["contenido"]
        cursor.execute("UPDATE posts SET titulo=?, contenido=? WHERE id=?", (titulo, contenido, post_id))
        conn.commit()
        conn.close()
        flash("Post actualizado exitosamente", "success")
        return redirect(url_for("profile", user_id=session.get("user_id")))
    
    conn.close()
    return render_template("edit_post.html", post=post)


@app.route("/post/<int:post_id>/delete", methods=["POST"])
def delete_post(post_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Opcional: verificar que el usuario sea dueño del post
    cursor.execute("SELECT user_id FROM posts WHERE id=?", (post_id,))
    post_user = cursor.fetchone()
    if post_user and post_user[0] != session.get("user_id"):
        flash("No puedes borrar este post", "danger")
        return redirect(url_for("profile", user_id=session.get("user_id")))

    cursor.execute("DELETE FROM posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    flash("Post eliminado exitosamente", "success")
    return redirect(url_for("profile", user_id=session.get("user_id")))


# 🔹 Acerca de
@app.route("/about")
def about():
    if "user_id" in session:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE id=?", (session["user_id"],))
        user = cursor.fetchone()
        conn.close()
        return render_template("about.html", user=user)
    return render_template("about.html", user=None)


if __name__ == "__main__":
    app.run(debug=True)
