import os
import bcrypt
import pymysql
from dotenv import load_dotenv
from flask import Flask, render_template, request, session, redirect

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")


@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


def get_db():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def validate_title(title):
    if title == "":
        return "Title is required"
    if len(title) > 200:
        return "Title is too long (200 characters at most)"
    return None


def load_todos(filter_by):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT todo_id, title, is_done, created_at FROM todos WHERE user_id = %s ORDER BY todo_id DESC",
        (session["user_id"],),
    )
    all_todos = cursor.fetchall()
    db.close()

    if filter_by == "open":
        todos = [t for t in all_todos if not t[2]]
    elif filter_by == "done":
        todos = [t for t in all_todos if t[2]]
    else:
        todos = all_todos
    return todos, len(all_todos)


def show_todos(add_error="", edit_error="", edit_id=None, add_value="", edit_value=""):
    filter_by = request.args.get("filter", "all")
    if filter_by not in ("all", "open", "done"):
        filter_by = "all"
    todos, total = load_todos(filter_by)
    return render_template(
        "todos.html",
        name=session["name"],
        todos=todos,
        filter_by=filter_by,
        total=total,
        add_error=add_error,
        edit_error=edit_error,
        edit_id=edit_id,
        add_value=add_value,
        edit_value=edit_value,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        errors = {}
        if name == "":
            errors["name"] = "Name is required"
        if email == "":
            errors["email"] = "Email is required"
        if password == "":
            errors["password"] = "Password is required"
        if confirm_password == "":
            errors["confirm_password"] = "Confirm password is required"
        elif password != "" and password != confirm_password:
            errors["confirm_password"] = "Passwords do not match"

        if errors:
            return render_template(
                "register.html", errors=errors, name=name, email=email
            )

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s)",
                (email, name, password_hash),
            )
            db.commit()
            session["user_id"] = cursor.lastrowid
            session["name"] = name
        except pymysql.err.IntegrityError:
            db.close()
            errors["email"] = "Email Already Exists"
            return render_template(
                "register.html", errors=errors, name=name, email=email
            )
        db.close()
        return redirect("/")

    return render_template("register.html", errors={}, name="", email="")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"]

        errors = {}
        if email == "":
            errors["email"] = "Email is required"
        if password == "":
            errors["password"] = "Password is required"
        if errors:
            return render_template("login.html", errors=errors, email=email)

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT user_id, name, password_hash FROM users WHERE email = %s",
            (email,),
        )
        user = cursor.fetchone()
        db.close()

        if user is None or not bcrypt.checkpw(
            password.encode("utf-8"), user[2].encode("utf-8")
        ):
            errors["general"] = "Invalid email or password"
            return render_template("login.html", errors=errors, email=email)

        session["user_id"] = user[0]
        session["name"] = user[1]
        return redirect("/")

    return render_template("login.html", errors={}, email="")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect("/login")
    return show_todos()


@app.route("/add", methods=["POST"])
def add():
    if "user_id" not in session:
        return redirect("/login")

    title = request.form["title"].strip()
    error = validate_title(title)
    if error:
        return show_todos(add_error=error, add_value=title)

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO todos (user_id, title) VALUES (%s, %s)",
        (session["user_id"], title),
    )
    db.commit()
    db.close()

    return redirect("/")


@app.route("/edit/<int:todo_id>", methods=["POST"])
def edit(todo_id):
    if "user_id" not in session:
        return redirect("/login")

    title = request.form["title"].strip()
    error = validate_title(title)
    if error:
        return show_todos(edit_error=error, edit_id=todo_id, edit_value=title)

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE todos SET title = %s WHERE todo_id = %s AND user_id = %s",
        (title, todo_id, session["user_id"]),
    )
    db.commit()
    db.close()

    return redirect(request.referrer or "/")


@app.route("/toggle/<int:todo_id>", methods=["POST"])
def toggle(todo_id):
    if "user_id" not in session:
        return redirect("/login")

    is_done = int(request.form["is_done"])

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE todos SET is_done = %s WHERE todo_id = %s AND user_id = %s",
        (is_done, todo_id, session["user_id"]),
    )
    db.commit()
    db.close()

    return redirect(request.referrer or "/")


@app.route("/delete/<int:todo_id>", methods=["POST"])
def delete(todo_id):
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM todos WHERE todo_id = %s AND user_id = %s",
        (todo_id, session["user_id"]),
    )
    db.commit()
    db.close()

    return redirect(request.referrer or "/")


if __name__ == "__main__":
            app.run(debug=True)