import os   

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, is_pass_strong

# Configure application
app = Flask(__name__)
app.debug = True
app.secret_key = 'development key'

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get transctin details from sql table
    transactions = db.execute("SELECT symbol, SUM(shares) as total_shares, price FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0", 
                                                                                            user_id=session["user_id"])

    # symbols = db.execute("SELECT symbol price FROM transactions WHERE user_id = :user_id", 
    #                                     user_id=session["user_id"])

    # Get userCash from sql table
    user_cash = db.execute("SELECT cash FROM users WHERE id = :user_id",
                                            user_id = session["user_id"])
    
    quotes = {}
    pridected_cash = 0.0
    
    for transaction in transactions:
        quotes[transaction["symbol"]] = lookup(transaction["symbol"])
        pridected_cash += float(quotes[transaction["symbol"]]["price"] * transaction["total_shares"])
    
    # for symbol in symbols:
    #     pridected_cash += float(quotes[symbol[0]["symbol"]]["price"])
    
    pridected_cash = round((pridected_cash + user_cash[0]["cash"]), 4)
    
    return render_template("index.html", transactions = transactions, user_cash = user_cash, quotes = quotes, pridected_cash = round(pridected_cash, 4))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    
    # If method is post meaning user is intracting wiht form go ahead
    if request.method == "POST":
        # Look for the symbol user entered using lookup
        quote = lookup(request.form.get("symbol"))
        # through err if can't find the sym
        if quote == None:
            return apology("invalid symbol", 400)
        # try except for throughing err if user entred negative value
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("shares must be a positive integer", 400)
        
        if (shares <= 0):
            return apology("Must buy atleast one share", 400)
        # Read user cash from db
        userCash = db.execute("SELECT cash FROM users WHERE id = :user_id",
                                               user_id = session["user_id"])
        
        cost = shares * quote["price"]
        
        # through err if user has less money
        if (cost > userCash[0]["cash"]):
            return apology("You don't have enough money to buy that")
        
        db.execute("UPDATE users SET cash = cash - :cost WHERE id = :user",
                            cost = cost, user = session["user_id"])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES(:user_id, :symbol, :shares, :price)",
                    user_id = session["user_id"],
                    symbol = request.form.get("symbol"),
                    shares = shares,
                    price = quote["price"])
        flash("Bought!")

        return redirect("/")
    else: 
        return render_template("buy.html")
        


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    
    transactions = db.execute("SELECT symbol, shares, price, created_at FROM transactions WHERE user_id = :user_id", 
                                                                                            user_id=session["user_id"])
    return render_template("history.html", transactions = transactions)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        if quote == None:
            return apology("invalid symbol", 400)

        return render_template("quoted.html", quote=quote)

    # User reached route via GET (as by clicking a link or via redi)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        password = request.form.get("password")
        # Ensure username was submitted
        if not password:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password and confirmation match
        elif not request.form.get("password") == request.form.get("rpassword"):
            return apology("passwords do not match", 400)
        
        # Check if password is strong function in helper.py
        elif not is_pass_strong(password):
            return apology("You must have atleast 2 numbers 2 special character and 2 alphabets", 400)
        
        # hash the password and insert a new user in the database
        hash = generate_password_hash(request.form.get("password"))
        new_user_id = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                                username=request.form.get("username"),
                                hash=hash)

        # unique username constraint violated?
        if not new_user_id:
            return apology("username taken", 400)
    
        # new_user_id = db.execute("SELECT id FROM users WHERE username=:username;", 
        #                                     username=request.form.get("username"))
        # # unique username constraint violated?
        # if not new_user_id:
        #     return apology("username taken", 400)

        # if db.execute("SELECT id FROM users WHERE username=:username;", username=request.form.get("username"))


        # Remember which user has logged in
        session["user_id"] = new_user_id
    

        # Display a flash message
        flash("Registered!")

        # Redirect user to home page
        return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html") 



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        # Check if the symbol exists
        if quote == None:
            return apology("invalid symbol", 400)
        try:
            shares_to_sell = int(request.form.get("shares"))
        except:
            return apology("share must be a positive number", 400)
        if shares_to_sell <= 0:
            apology("can't sell less than 1 shares")
        price_per_share = quote["price"]
        
        shares_user_have = db.execute("SELECT SUM(shares) as total_shares, price FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0", 
                                                                                        user_id=session["user_id"])

        
        if shares_to_sell > shares_user_have[0]["total_shares"]:    
            return apology("Not enough shares to sell", 403)
        
        cost = shares_to_sell * price_per_share

        db.execute("UPDATE users SET cash = cash + :cost WHERE id = :user",
                            cost = cost, user = session["user_id"])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES(:user_id, :symbol, :shares, :price)",
                    user_id = session["user_id"],
                    symbol = request.form.get("symbol"),
                    shares = -shares_to_sell,
                    price = price_per_share)

        flash("Sold!")

        return redirect("/")
    else:
        quotes = db.execute("SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0", 
                                                                              user_id=session["user_id"])

        return render_template("sell.html", quotes = quotes)


@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    if request.method == "POST":
        new_password = request.form.get("cpassword")
        re_new_password = request.form.get("crpassword")
        
        if not new_password:
            return apology("You must enter a password", 402)
            
        elif not re_new_password:
            return apology("You must enter a password", 402)
        
        elif new_password != re_new_password:
            return apology("New password did not match", 403)

        hash = generate_password_hash(new_password)
        db.execute("UPDATE users SET hash = :hash WHERE id = :user_id", 
                                hash=hash, user_id=session["user_id"])
        
        flash("Changed!")

        return redirect("/")
    
    return render_template("password.html")

@app.route("/wallet", methods=["GET", "POST"])
@login_required
def wallet():
    if request.method == "POST":
        cash = request.form.get("cash")
        
        if not cash:
            return apology("Enter Cash")
        elif cash <= 0:
            return apology("Cash should be more than 0")
        db.execute("UPDATE users SET cash = cash + :cash WHERE id = :user",
                                    cash = cash, user = session["user_id"])
        flash("Cash Added!")    
        return redirect("/")
    
    return render_template("wallet.html")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
