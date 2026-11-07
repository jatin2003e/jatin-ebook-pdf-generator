import os, sqlite3, secrets, functools
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, send_file, jsonify
from dotenv import load_dotenv
load_dotenv()
app=Flask(__name__)
app.secret_key=os.getenv('SECRET_KEY') or secrets.token_hex(32)
app.config['MAX_CONTENT_LENGTH']=5*1024*1024
DATA=Path('instance');DATA.mkdir(exist_ok=True)
DB=DATA/'app.sqlite3'
APP_NAME='Ebook PDF Generator'
@app.context_processor
def context():return dict(app_name=APP_NAME)
def conn():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init(sql):
 with conn() as c:c.executescript(sql)
def admin_required(fn):
 @functools.wraps(fn)
 def wrapped(*args,**kwargs):
  if not session.get('admin'):return redirect('/login')
  return fn(*args,**kwargs)
 return wrapped
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  if os.getenv('ADMIN_PASSWORD') and secrets.compare_digest(request.form.get('password',''),os.getenv('ADMIN_PASSWORD')):
   session.clear();session['admin']=True;return redirect('/dashboard')
  flash('Incorrect password')
 return render_template('login.html',title='Admin login')
@app.post('/logout')
def logout():session.clear();return redirect('/')

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from xml.sax.saxutils import escape
from io import BytesIO
init("""CREATE TABLE IF NOT EXISTS books(id INTEGER PRIMARY KEY,title TEXT,author TEXT,chapters TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);""")
@app.get('/')
def home():return render_template('pdf_home.html',title='PDF Studio')
@app.route('/dashboard',methods=['GET','POST'])
@admin_required
def dashboard():
 if request.method=='POST':
  title=request.form.get('title','').strip()[:200];chapters=request.form.get('chapters','').strip()[:50000]
  if not title or not chapters:abort(400)
  with conn() as c:c.execute('INSERT INTO books(title,author,chapters) VALUES(?,?,?)',(title,request.form.get('author','')[:100],chapters))
  return redirect('/dashboard')
 with conn() as c:books=c.execute('SELECT * FROM books ORDER BY id DESC').fetchall()
 return render_template('pdf_admin.html',title='Your books',books=books)
@app.get('/export/<int:bid>')
@admin_required
def export(bid):
 with conn() as c:b=c.execute('SELECT * FROM books WHERE id=?',(bid,)).fetchone()
 if not b:abort(404)
 out=BytesIO();doc=SimpleDocTemplate(out,pagesize=(595,842),rightMargin=58,leftMargin=58,topMargin=60,bottomMargin=60)
 styles=getSampleStyleSheet();story=[Paragraph(escape(b['title']),styles['Title']),Spacer(1,25),Paragraph('By '+escape(b['author'] or 'Anonymous'),styles['Heading2']),PageBreak()]
 for chapter in b['chapters'].split('\n\n'):
  lines=chapter.strip().splitlines()
  if not lines:continue
  story.append(Paragraph(escape(lines[0]),styles['Heading2']))
  for line in lines[1:]:
   if line.strip():story.extend([Paragraph(escape(line),styles['BodyText']),Spacer(1,10)])
  story.append(Spacer(1,16))
 doc.build(story);out.seek(0)
 return send_file(out,mimetype='application/pdf',as_attachment=True,download_name=f'ebook-{bid}.pdf')
if __name__=='__main__':app.run(port=int(os.getenv('PORT',5000)))
