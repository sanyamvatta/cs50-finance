import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    userId = session['user_id']
    try:
        user = db.execute("SELECT * FROM users WHERE id = ?", userId)[0]
        transactions = db.execute("SELECT * FROM transactions WHERE user_id = ?",userId)
    except:
        return apology("Server error couldnt find user. Please try again")

    stocks = {}
    
    for transaction in transactions:
        if transaction['symbol'] not in stocks:
            stocks[transaction['symbol']] = int(transaction['shares'])
        elif transaction['type'] == "buy":
            stocks[transaction['symbol']] += int(transaction['shares'])
        elif transaction['type'] == "sell":
            stocks[transaction['symbol']] -= int(transaction['shares'])
            if stocks[transaction['symbol']] == 0:
                stocks.pop(transaction['symbol'])

    
    prices = {}

    for stock in stocks:
        currentStock = lookup(stock)
        prices[stock] = float(currentStock['price'])
    
    portfolioPrices = {}

    for stock in stocks:
        currentStock = lookup(stock)
        portfolioPrices[stock] = prices[stock] * stocks[stock]

    portfolioVal = 0

    for price in portfolioPrices:
        portfolioVal += portfolioPrices[price]
        
    
    totalUserVal = float(user['cash']) + portfolioVal

    return render_template('index.html',usd=usd, portfolio = stocks, portfolioVal = portfolioVal, totalUserVal = totalUserVal,prices = prices,portfolioPrices = portfolioPrices,userCash = usd(user['cash']))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("stock")
        stock = lookup(symbol)
        if not stock:
            return apology("Stock not found")

        try:
            quantity = float(request.form.get("shares"))
        except:
            return apology("Quantity must be a valid integer")
        if quantity < 0:
            return apology("Quantity must be greater than zero")
        elif quantity != int(quantity):
            return apology("Quantity must be an integer")

        userId = session["user_id"]
        try:
            user = db.execute("SELECT * FROM users WHERE id = ?",userId)
        except:
            return apology("Server error")

        balance = int(user[0]['cash'])

        spend = float(stock['price']) * int(quantity)

        if spend > balance:
            return apology("Not enough funds to make the transaction")
        
        db.execute("UPDATE users SET cash =? WHERE id = ?",balance-spend,userId)

        try:
            db.execute("INSERT INTO transactions (user_id,symbol,shares,price,timestamp,type) VALUES (?,?,?,?,CURRENT_TIMESTAMP,?)",userId,symbol,quantity,lookup(symbol)['price'],"buy")
        except:
            return apology("Transaction not recorded server error. Please try again")

        return redirect('/')


@app.route("/history")
@login_required
def history():
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY datetime(timestamp)",session['user_id'])
    return render_template('history.html',transactions=transactions,float = float, usd = usd)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Invalid symbol")
        else:
            stock = lookup(symbol)
            if not stock:
                return apology("Stock not found")
            return render_template("quoted.html", stock=stock,usd =usd)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        user_in_db = db.execute("SELECT * FROM users WHERE username = ?",username)
        if not request.form.get("username"):
            return apology("Please enter a username")
        elif user_in_db:
            return apology("Username already taken")
        elif not request.form.get("password"):
            return apology("Please enter a password")
        elif not request.form.get("confirmation"):
            return apology("Please confirm your password")
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Password and confirm password should be same")
        
        password = generate_password_hash(request.form.get("password"))

        try:
            db.execute("INSERT INTO users (username,hash) VALUES (?, ?)",username,password)
            return redirect('/login')
        except:
            return apology("Coult not register")


        
        


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    stocks=db.execute(''' SELECT symbol, SUM(CASE WHEN type = 'buy' THEN shares WHEN type = 'sell' THEN -shares END) as total_shares 
            FROM transactions 
            WHERE user_id = ? 
            GROUP BY symbol''',session['user_id'])
    
    if request.method == "GET":
        return render_template("sell.html",stocks=stocks)
    else:
        userId = session['user_id']
        symbol = request.form.get('sname')
        number = int(request.form.get('nshares'))
        stock = db.execute(''' SELECT symbol, SUM(CASE WHEN type = 'buy' THEN shares WHEN type = 'sell' THEN -shares END) as total_shares 
                            FROM transactions 
                            WHERE user_id = ? AND symbol = ?
                            GROUP BY symbol''',userId,symbol)
        if number <= 0:
            return apology("Number of shares cannot be negative")
        
        if number > stock[0]['total_shares']:
            return apology("You don't have enough shares to sell")
        
        price = lookup(symbol)['price']

        total_price = price*number

        try:
            user = db.execute("SELECT * FROM users WHERE id =?",userId)
            newCash = float(user[0]['cash']) + total_price
            db.execute("UPDATE users SET cash = ? WHERE id = ?",newCash,userId)
            db.execute("INSERT INTO transactions (user_id,symbol,shares,price,timestamp,type) VALUES (?,?,?,?,CURRENT_TIMESTAMP,?)",userId,symbol,number,price,"sell")
            return redirect('/')
        except:
            return apology("Could not register transaction. Please try again later.")


@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    if request.method == "GET":
        return render_template("cash.html")
    else:
        cash = float(request.form.get("cash"))

        if cash > 10000 or cash <= 0:
            return apology("Cash added can not be less than 0 or more than 10000")
        userId = session['user_id']
        try:
            user = db.execute("SELECT * FROM users WHERE id =?",userId)
            newCash = float(user[0]['cash']) + cash
            db.execute("UPDATE users SET cash = ? WHERE id = ?",newCash,userId)
            return redirect('/')
        except:
            return apology("Could not make the transaction. Please try again later.")



                