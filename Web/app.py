from flask import Flask, render_template, request, redirect, session, flash, url_for
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

# 🔹 Configuración básica de Flask
app = Flask(__name__)
app.secret_key = "supersecreto123"  # Clave secreta para sesiones
DB_NAME = "database.db"  # Nombre de la base de datos SQLite

# 🔹 Configuración de carpeta para avatars (aunque actualmente no se usan)
UPLOAD_FOLDER = "static/avatars/"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 🔹 Función para validar extensiones de archivos permitidas
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# 🔹 Inicializar la base de datos y crear tablas si no existen
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Tabla de usuarios
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

    # Tabla de posts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            titulo TEXT,
            contenido TEXT,
            fecha TEXT,
            etiquetas TEXT DEFAULT ''
        )
    """)

    # Tabla de comentarios
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

    # Tabla de likes
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

# 🔹 Inicializar base de datos al iniciar la app
init_db()

# 🔹 Función global para inyectar información del usuario en todas las plantillas
@app.context_processor
def inject_user():
    user_data = None
    if "user_id" in session:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, bio, avatar FROM usuarios WHERE id=?", (session["user_id"],))
        user_data = cursor.fetchone()
        conn.close()
    return dict(current_user=user_data, current_year=datetime.utcnow().year)

# 🔹 Rutas de autenticación
@app.route("/")
def home():
    # Redirige al login si no hay sesión, sino al index
    return redirect("/login") if "user_id" not in session else redirect("/index")

@app.route("/register", methods=["GET", "POST"])
def register():
    # Registro de usuario
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
    # Login de usuario
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
    # Cierra sesión del usuario
    session.clear()
    flash("Has cerrado sesión", "info")
    return redirect("/login")

# 🔹 Página principal
@app.route("/index")
def index():
    # Asegura que el usuario esté logueado
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

# 🔹 Crear un nuevo post
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

# 🔹 Ver post individual y sus comentarios
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
    # Obtener comentarios
    cursor.execute("""
        SELECT comentarios.id, comentarios.contenido, comentarios.fecha, usuarios.username, comentarios.user_id
        FROM comentarios JOIN usuarios ON comentarios.user_id=usuarios.id
        WHERE comentarios.post_id=?
        ORDER BY comentarios.id ASC
    """, (post_id,))
    comentarios = cursor.fetchall()
    # Verificar si el usuario actual dio like
    cursor.execute("SELECT * FROM likes WHERE post_id=? AND user_id=?", (post_id, session["user_id"]))
    liked = cursor.fetchone() is not None
    conn.close()
    return render_template("view_post.html", post=post, comentarios=comentarios, liked=liked)

# 🔹 Añadir comentario a un post
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

# 🔹 Dar like o quitar like de un post
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

# 🔹 Página de perfil del usuario (sin avatar)
@app.route("/profile/<int:user_id>")
def profile(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, bio FROM usuarios WHERE id=?", (user_id,))
    user = cursor.fetchone()

    # Obtener posts del usuario
    cursor.execute("""
        SELECT p.id, p.titulo, p.contenido, p.fecha,
               (SELECT COUNT(*) FROM comentarios c WHERE c.post_id=p.id) AS comentarios_count,
               (SELECT COUNT(*) FROM likes l WHERE l.post_id=p.id) AS likes_count
        FROM posts p
        WHERE p.user_id=?
        ORDER BY p.fecha DESC
    """, (user_id,))
    posts = cursor.fetchall()
    conn.close()
    return render_template("profile.html", user=user, posts=posts)

# 🔹 Editar post existente
@app.route("/post/<int:post_id>/edit", methods=["GET", "POST"])
def edit_post(post_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
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
# 🔹 Borrar post vía AJAX
@app.route("/post/<int:post_id>/delete", methods=["DELETE"])
def delete_post(post_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Verificar que el post pertenece al usuario
    cursor.execute("SELECT user_id FROM posts WHERE id=?", (post_id,))
    post_user = cursor.fetchone()
    if not post_user:
        conn.close()
        return {"status": "error", "message": "Post no encontrado"}, 404

    if post_user[0] != session.get("user_id"):
        conn.close()
        return {"status": "error", "message": "No puedes borrar este post"}, 403

    # Borrar post
    cursor.execute("DELETE FROM posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()

    return {"status": "success", "message": "Post eliminado exitosamente"}

# 🔹 Página "Acerca de"
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

# 🔹 Ejecutar app
if __name__ == "__main__":
    app.run(debug=True)
