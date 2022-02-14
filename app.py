from flask import Flask, request, jsonify,redirect
from flask_cors import CORS
import RPi.GPIO as GPIO
import time
from apscheduler.schedulers.background import BackgroundScheduler
import requests


GPIO.setmode(GPIO.BOARD)
GPIO.setup(3,GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(5,GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(7,GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(11,GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(37,GPIO.OUT)
GPIO.setup(35,GPIO.OUT)
GPIO.setup(33,GPIO.OUT)
GPIO.setup(31,GPIO.OUT)

pieces=[3,5,7,11]
libeles=["Chambre1","Chambre2","Salon","Cuisine"]
allum_desir=[False,False,False,False]
IS_AUTO=[False,False,False,False]
r1= GPIO.PWM(37,50)
r1.start(0)
r2= GPIO.PWM(35,50)
r2.start(0)
r3= GPIO.PWM(33,50)
r3.start(0)
r4= GPIO.PWM(31,50)
r4.start(0)
rideaux=[r1,r2,r3,r4]
etat_rid=["Fermé","Fermé","Fermé","Fermé"]


def setupangle(angle,p):
    duty=0.056*angle + 2.5
    GPIO.output(37,True)
    p.ChangeDutyCycle(duty)
    time.sleep(0.2)
    GPIO.output(37,False)
    p.ChangeDutyCycle(0)
    
def rc_count():
    PIN=15
    count=0
    GPIO.setup(PIN,GPIO.OUT)
    GPIO.output(PIN,GPIO.LOW)
    time.sleep(0.1)
    GPIO.setup(PIN,GPIO.IN)
    while GPIO.input(PIN)==GPIO.LOW:
        count+=1
    return count

def resistance():
    etats=[GPIO.input(i) for i in pieces]
    count=rc_count()
    for i,j in zip(pieces,etats):
        if j==GPIO.HIGH and count<70000 and not allum_desir[pieces.index(i)] and IS_AUTO[pieces.index(i)]:
            GPIO.output(i,GPIO.LOW)
        elif j==GPIO.HIGH and count<70000:
            allum_desir[pieces.index(i)]=False
    if count>70000 and IS_AUTO.all():
        url_to_post=f"http://0.0.0.0:5000/maison/rideaux/master/0"
        requests.post(url_to_post)
    elif count<70000 and IS_AUTO.all():
        url_to_post=f"http://0.0.0.0:5000/maison/rideaux/master/1"
        requests.post(url_to_post)
    else:
        for i in range(4):
            if count>70000 and IS_AUTO[i]:
                url_to_post=f"http://0.0.0.0:5000/maison/rideaux/{i+1}/0"
                requests.post(url_to_post)
            elif count<70000 and IS_AUTO[i]:
                url_to_post=f"http://0.0.0.0:5000/maison/rideaux/{i+1}/1"
                requests.post(url_to_post)
    print(rc_count())
    
for i in rideaux:
    setupangle(90,i)
    setupangle(0,i)
    
    
    
sched=BackgroundScheduler(daemon=True)
sched.add_job(resistance,'interval',seconds=10)
sched.start()

app=Flask(__name__)
cors=CORS(app,resources={r'/*':{'origins':'*'}})
@app.route("/",methods=['GET'])
def test():
    return print("succes")
@app.route("/maison/light/<int:piece>/<int:etat>" ,methods=['POST'])
def allumage(piece,etat):
    etat= GPIO.HIGH if etat==1 else GPIO.LOW
    allum_desir[pieces.index(piece)]=True if etat==GPIO.HIGH else False
    GPIO.output(piece,etat)
    return jsonify('Done'),200

@app.route("/maison/light/<int:piece>/toggle" ,methods=['POST'])
def toggle(piece):
    if GPIO.input(piece)==GPIO.HIGH :
        GPIO.output(piece,GPIO.LOW)
        state="Éteint"
    else :
        GPIO.output(piece,GPIO.HIGH)
        state="Allumé"
        allum_desir[pieces.index(piece)]=True
        print(allum_desir)
    salle=libeles[pieces.index(piece)]
    return jsonify({salle:state}),200        
    
@app.route("/maison/light" ,methods=['GET'])
def etats():
    etats=["Allumé" if GPIO.input(i)==GPIO.HIGH else "Éteint" for i in pieces]
    reponse={str(i):j for i,j in zip(libeles,etats)} 
    return jsonify(reponse)

@app.route("/maison/rideaux" ,methods=['GET'])
def etatsr():
    reponse={str(i):j for i,j in zip(libeles,etat_rid)} 
    return jsonify(reponse)

@app.route("/maison/rideaux/<int:piece>/<int:etat>" ,methods=['POST'])
def ouverture_rideau(etat,piece):
    if piece==1:
        rid=r1
    elif piece==2:
        rid=r2
    elif piece==3:
        rid=r3
    elif piece==4:
        rid=r4
    else:
        rid=None
    condition=etat_rid[piece-1] if rid is not None else None
    if etat ==1:
        print(condition)
        if condition=="Fermé":
            setupangle(90,rid)
            setupangle(180,rid)
            etat_rid[rideaux.index(rid)]="Ouvert"
            if condition is not None:
                return jsonify({libeles[piece-1]:etat_rid[piece-1]}),200
            else:
                return 'Piece non valide',404
    elif etat==0:
        if condition=="Ouvert":
            setupangle(90,rid)
            setupangle(0,rid)
            etat_rid[rideaux.index(rid)]="Fermé"
        return jsonify({libeles[rideaux.index(rid)]:"Fermé"})if condition is not None else 'Hola',200
    else:
        return jsonify({libeles[rideaux.index(rid)]:"État non valide"})if rid is not None else 'To come',200
    
@app.route('/maison/auto', methods=['GET'])
def isautol():
    respones={i+"_mode_auto":j for i,j in zip(libeles,IS_AUTO)}
    return jsonify(respones),200

@app.route('/maison/master/<int:piece>/<int:etat>', methods=['POST'])
def setautop(piece,etat):
    if piece >3 or piece<0:
        return "Piece non valide",404
    if etat==1:
        IS_AUTO[piece-1]=True
        return jsonify({libeles[piece-1]+"_mode_auto":True}),200
    elif etat==0:
        IS_AUTO[piece-1]=False
        return jsonify({libeles[piece-1]+"_mode_auto":False}),200
    else:
        return "Etat non valise",404

@app.route('/maison/master/auto/<int:etat>', methods=['POST'])
def setautol(etat):
    if etat ==1:
        for i in range(4):
            IS_AUTO[i]=True
        respones={i+"_mode_auto":j for i,j in zip(libeles,IS_AUTO)}
        return jsonify(respones),200
    elif etat==0:
        for i in range(4):
            IS_AUTO[i]=False
        respones={i+"_mode_auto":j for i,j in zip(libeles,IS_AUTO)}
        return jsonify(respones),200
    else:
        return 'Numero de piece non valide',404
    
@app.route('/maison/light/master/<int:etat>', methods=["POST"])
def masterlum(etat):
    etat=GPIO.HIGH if etat==1 else GPIO.LOW if etat==0 else None
    if etat is None:
        return jsonify("etat non valide"),404
    else:
        for i in pieces:
            GPIO.output(i,etat)
        return jsonify({i:"Allumé" if etat==GPIO.HIGH else 'Eteint' for i in libeles}),200

@app.route('/maison/rideaux/master/<int:etat>', methods=["POST"])
def masterid(etat):
    etat=etat if etat in [1,0] else None
    if etat is None:
        return jsonify("État non valide"),404
    else:
        for i in range(len(rideaux)):
            if etat_rid[i]=="Fermé" and etat==1:
                setupangle(90,rideaux[i])
                setupangle(180,rideaux[i])
                etat_rid[i]="Ouvert"
            elif etat_rid[i]=="Ouvert" and etat==0:
                setupangle(90,rideaux[i])
                setupangle(0,rideaux[i])
                etat_rid[i]="Fermé"
        return jsonify({i:j for i,j in zip(libeles,etat_rid)}),200



if __name__=='__main__':
    app.run(debug=True,port=8080,host='0.0.0.0')
    
        

