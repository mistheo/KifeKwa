# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, url_for, redirect, session
import locale
from datetime import datetime, timedelta
import sqlite3 as sql
from pathlib import Path
import hashlib

# CONSTANTES
DATABASE_PATH = 'projet.db'
SCRIPTSQL_PATH = 'script.sql'

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'  # Clé secrète pour le chiffrement du cookie de session
app.permanent_session_lifetime = timedelta(minutes=30)  # Durée de vie de la session : 30 min

# INITIALISATION DE LA BASE DE DONNÉES
db_path = Path(DATABASE_PATH)
if not db_path.exists():
    script_path = Path(SCRIPTSQL_PATH)
    
    with script_path.open() as script_file:
        script = script_file.read()
    
    con = sql.connect(DATABASE_PATH)
    cur = con.cursor()
    cur.executescript(script)
    con.commit()
    con.close()
else:
    sql.connect(DATABASE_PATH)

# FILTRE JINJA TEMPLATE POUR LE FORMATAGE DES DATES
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%A %d %B'):
    locale.setlocale(locale.LC_ALL, 'fr_FR.UTF-8')
    date_obj = datetime.strptime(value, '%Y-%m-%d')
    return date_obj.strftime(format)

# GESTIONNAIRE D'ERREUR
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(502)
def page_not_found(error):
    return render_template('error.html')

# PAGE D'ACCUEIL
@app.route('/')
def displayIndexPage():
    return render_template('index.html')

# PAGE DE CONNEXION
@app.route('/login')
def displayLoginPage():
    if session.get('logged_in'):
        return redirect(url_for('displayApplication'))
    else:
        isError = request.args.get('failToLog')
        return render_template('login.html', failToLog=isError)

# PAGE D'INSCRIPTION
@app.route('/register')
def displayRegisterPage():
    if session.get('logged_in'):
        return redirect(url_for('displayApplication'))
    else:
        msg = request.args.get('errorMsg')
        return render_template('register.html', errorMsg=msg)

# INSCRIPTION À L'APPLICATION
@app.route('/register/new', methods=['POST'])
def registerToApplication():
    newUserName = request.form['username']
    newUserPass = request.form['password']
    newUserPassConf = request.form['confirm-password']
    newUserNick = request.form['nickname']
       
    if not(newUserPass == newUserPassConf):
        return redirect(url_for('displayRegisterPage', errorMsg="Les mots de passe ne sont pas identiques"))
    elif getUserPasswordDB(newUserName, newUserPass):
        return redirect(url_for('displayRegisterPage', errorMsg="Ce nom d'utilisateur est déjà utilisé."))
    elif newUserNick == "":
        newUserNick = newUserName
            
    addUserPasswordDB(newUserName, newUserPass, newUserNick)
    return redirect(url_for('displayLoginPage'))
            
# CONNEXION
@app.route('/connect', methods=['POST'])
def connectToApplication():
    user = request.form["username"]
    password = request.form["password"]

    userData = getUserPasswordDB(user, password)
    
    if userData:
        session['logged_in'] = True
        session['userData'] = userData
        
        return redirect(url_for('displayApplication'))
    else:
        return redirect(url_for('displayLoginPage', failToLog=True))

# PAGE DE L'APPLICATION
@app.route('/monagenda')
def displayApplication():
    if session.get('logged_in'):
        nick = session.get('userData')[3]
        userId = session.get('userData')[0]
        
        events = getEventsByUserDB(userId)
        
        if events and events[0][3] == datetime.today().strftime('%Y-%m-%d'):
            isEventIsToday = 'today'
        else:
            isEventIsToday = 'next'
            
        if session.get('userData')[4] >= 2:
            isMaster = True
        else:
            isMaster = False
        
        return render_template('appli.html', nickname=nick, eventsList=events, isEventIsToday=isEventIsToday, isMasterAccount=isMaster)
    else:
        return redirect(url_for('displayLoginPage'))

# MODIFICATION D'UN ÉVÉNEMENT EXISTANT
@app.route('/monagenda/event/<int:idEvent>', methods=['GET'])
def displayApplicationModifyEvent(idEvent):
    if session.get('logged_in'):
        nick = session.get('userData')[3]
        userId = session.get('userData')[0]
        
        event = getEventByIdDB(idEvent)                
        
        if event and event[4] == userId:
            return render_template('recap_event.html', eventName=event[1], eventDesc=event[2], eventDate=event[3], today=datetime.today().strftime('%Y-%m-%d'), nickname=nick, eventMode='M', urlPost="/monagenda/event/modify/"+str(idEvent), idEvent=idEvent)
        
    return redirect(url_for('displayLoginPage'))

@app.route('/monagenda/event/modify/<int:idEvent>', methods=['POST'])
def applicationUpdateEvent(idEvent):
    if session.get('logged_in'):
        nick = session.get('userData')[3]
        userId = session.get('userData')[0]
        
        eventName = request.form["event-name"]
        eventDate = request.form["event-date"]
        eventDesc = request.form["event-desc"]
    
        
        event = getEventByIdDB(idEvent)                
        if event and event[4] == userId:
            updateEventByIdDB(idEvent, eventName, eventDesc, eventDate)
            return redirect(url_for('displayApplication'))
        
    return redirect(url_for('displayLoginPage'))

# SUPPRESSION D'UN ÉVÉNEMENT
@app.route('/monagenda/event/delete/<int:idEvent>', methods=['GET'])
def ApplicationDelEvent(idEvent):
    if session.get('logged_in'):
        nick = session.get('userData')[3]
        userId = session.get('userData')[0]
        
        event = getEventByIdDB(idEvent)                
        if event and event[4] == userId:
            delEventByIdDB(idEvent)
            return redirect(url_for('displayApplication'))
        else:
            return redirect(url_for('displayApplicationNewEvent', errorMsg="L'événement ne peut pas être supprimé."))
    
    return redirect(url_for('displayLoginPage'))

# AJOUT D'UN ÉVÉNEMENT
@app.route('/monagenda/event/new', methods=['GET'])
def displayApplicationNewEvent():
    if session.get('logged_in'):
        nick = session.get('userData')[3]
        
        msg = request.args.get('errorMsg')
        return render_template('recap_event.html', today=datetime.today().strftime('%Y-%m-%d'), errorMsg=msg, nickname=nick, eventMode='A', urlPost="/monagenda/event/new")
    else:
        return redirect(url_for('displayLoginPage'))

@app.route('/monagenda/event/new', methods=['POST'])
def applicationNewEvent():
    if session.get('logged_in'):
        nick = session.get('userData')[3]
        userID = session.get('userData')[0]
        
        eventName = request.form["event-name"]
        eventDate = request.form["event-date"]
        eventDesc = request.form["event-desc"]
                
        if not getEventDB(eventName, eventDesc, eventDate, userID):
            addEventDB(eventName, eventDesc, eventDate, userID)
        else:
            return redirect(url_for('displayApplicationNewEvent', errorMsg="L'événement existe déjà"))
        
        return redirect(url_for('displayApplication'))
    else:
        return redirect(url_for('displayLoginPage'))

# DÉCONNEXION
@app.route('/disconnect')
def disconnectFromApplication():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('displayIndexPage'))

# FONCTIONS POUR LA BASE DE DONNÉES

def hashPassword(password):
    return hashlib.sha256(password.encode()).hexdigest()

def addUserPasswordDB(username, password, nickname):
    encodedPassword = hashPassword(password)
    con = sql.connect(DATABASE_PATH)
    cur = con.cursor()
    cur.execute('INSERT INTO user (username, passwordUser, nickname, type_user) VALUES (?, ?, ?, 1);', [username, encodedPassword, nickname]).fetchone()
    con.commit()
    con.close()

def getUserPasswordDB(username, password):
    con = sql.connect(DATABASE_PATH)
    cur = con.cursor()
    reponse = cur.execute("SELECT * FROM user WHERE username like ?;", [username]).fetchone()
    con.close()

    if reponse:
        hashedPassword = hashPassword(password)
        if reponse[2] == hashedPassword:
            return reponse
    return None
    
def getEventsByUserDB(idUser):
    con = sql.connect(DATABASE_PATH)
    cur = con.cursor()
    reponse = cur.execute("SELECT * FROM events WHERE createdBy=? ORDER BY dateevents ASC;",[idUser]).fetchall()
    con.close()
    
    return reponse

def getEventByIdDB(id):
    con = sql.connect(DATABASE_PATH)
    cur = con.cursor()
    reponse = cur.execute("SELECT * FROM events WHERE id=?;",[id]).fetchone()
    con.close()
    
    return reponse

def delEventByIdDB(id):
    con = sql.connect(DATABASE_PATH)
    cur = con.cursor()
    reponse = cur.execute("DELETE FROM events WHERE id = ?;",[id]).fetchone()
    con.commit()
    con.close()
    
    return reponse

def updateEventByIdDB(id,name,desc,date):
    con = sql.connect(DATABASE_PATH)
    cur = con.cursor()
    reponse = cur.execute("UPDATE events SET name =  ?, description = ? , dateevents = ? WHERE id=?;",[name,desc,date,id]).fetchone()
    con.commit()
    con.close()
    
    return reponse

def getAllEvents():
    con = sql.connect(DATABASE_PATH)
    cur = con.cursor()
    reponse = cur.execute("SELECT * FROM events;").fetchall()
    con.close()
    
    return reponse

def getEventDB(name,desc,date,who):
    con = sql.connect(DATABASE_PATH)
    cur = con.cursor()
    reponse = cur.execute("SELECT * from events WHERE name=? and description=? and dateevents=? and createdBy = ?;",[name,desc,date,who]).fetchone()
    con.close()
    
    return reponse

def addEventDB(name,desc,date,who):
    con = sql.connect(DATABASE_PATH)
    cur = con.cursor()
    cur.execute('INSERT INTO events (name, description, dateevents, createdBy) VALUES ( ?, ?, ?, ?);',[name,desc,date,who]).fetchone()
    con.commit()
    con.close()
