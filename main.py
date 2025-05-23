from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function
import requests
import os
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from email.utils import formataddr

load_dotenv()

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///leads.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)
db = SQLAlchemy(app)

with app.app_context():
    db.create_all()

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    charge = db.Column(db.String(200))
    court_date = db.Column(db.String(20))
    court_time = db.Column(db.String(20))
    court = db.Column(db.String(200))
    notes = db.Column(db.Text)
    homework = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    send_retainer = db.Column(db.Boolean, default=False)
    retainer_amount = db.Column(db.String(50))
    lvm = db.Column(db.Boolean, default=False)
    not_pc = db.Column(db.Boolean, default=False)
    quote = db.Column(db.String(50))

class CaseResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    defendant_name = db.Column(db.String(120))
    offense = db.Column(db.String(200))
    amended_charge = db.Column(db.String(200))
    disposition = db.Column(db.String(200))
    other_disposition = db.Column(db.String(200))
    jail_time_imposed = db.Column(db.String(50))
    jail_time_suspended = db.Column(db.String(50))
    fine_imposed = db.Column(db.String(50))
    fine_suspended = db.Column(db.String(50))
    license_suspension = db.Column(db.String(100))
    asap_ordered = db.Column(db.String(10))
    probation_type = db.Column(db.String(50))
    was_continued = db.Column(db.String(10))
    continuation_date = db.Column(db.String(20))
    client_email = db.Column(db.String(120))
    notes = db.Column(db.Text)
    date_disposition = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@app.route("/")
@login_required
def dashboard():
    case_results = CaseResult.query.order_by(CaseResult.created_at.desc()).all()
    return render_template("dashboard.html", case_results=case_results)

@app.route("/leads")
@login_required
def view_leads():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    return render_template("leads.html", leads=leads)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "dischley123":
            session["user"] = username
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/intake", methods=["GET", "POST"])
@login_required
def intake():
    if request.method == "POST":
        data = request.form

        new_lead = Lead(
            name=data.get("name"),
            phone=data.get("phone"),
            email=data.get("email"),
            charge=data.get("charge"),
            court_date=data.get("court_date"),
            court_time=data.get("court_time"),
            court=data.get("court"),
            notes=data.get("notes"),
            homework=data.get("homework"),
            send_retainer=False,
            lvm=False,
            not_pc=False,
            quote=None,
            retainer_amount=None
        )
        db.session.add(new_lead)
        db.session.commit()

        lead_url = url_for("view_lead", lead_id=new_lead.id, _external=True)

        msg = Message("New Client Intake Form Submission",
                      recipients=["attorneys@dischleylaw.com"],
                      sender=("New Lead", os.getenv('MAIL_DEFAULT_SENDER')))
        msg.body = f"""
New lead submitted:
Name: {new_lead.name}
Phone: {new_lead.phone}
Email: {new_lead.email}
Charge: {new_lead.charge}
Court Date: {new_lead.court_date}
Court Time: {new_lead.court_time}
Court: {new_lead.court}
Notes: {new_lead.notes}
Homework: {new_lead.homework}

Manage lead: {lead_url}
        """
        mail.send(msg)

        # Clio
        clio_payload = {
            "inbox_lead": {
                "from_first": new_lead.name.split()[0],
                "from_last": new_lead.name.split()[-1],
                "from_email": new_lead.email,
                "from_phone": new_lead.phone,
                "from_message": f"Charge: {new_lead.charge}, Notes: {new_lead.notes}, Homework: {new_lead.homework}",
                "referring_url": "http://127.0.0.1:5000/intake",
                "from_source": "Dischley Intake Form"
            },
            "inbox_lead_token": os.getenv("CLIO_TOKEN")
        }

        response = requests.post("https://grow.clio.com/inbox_leads", json=clio_payload)
        if response.status_code != 201:
            print("❌ Clio integration failed:", response.status_code, response.text)
        else:
            print("✅ Clio lead submitted successfully!")

        return redirect(url_for("intake_success"))
    return render_template("intake.html")

@app.route("/success")
def intake_success():
    return render_template("success.html")

@app.route("/lead/<int:lead_id>")
@login_required
def view_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    return render_template("view_lead.html", lead=lead)

@app.route("/lead/<int:lead_id>/update", methods=["POST"])
@login_required
def update_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)

    lead.name = request.form.get("name", lead.name)
    lead.phone = request.form.get("phone", lead.phone)
    lead.email = request.form.get("email", lead.email)
    lead.charge = request.form.get("charge", lead.charge)
    lead.court_date = request.form.get("court_date", lead.court_date)
    lead.court_time = request.form.get("court_time", lead.court_time)
    lead.court = request.form.get("court", lead.court)
    lead.notes = request.form.get("notes", lead.notes)
    lead.homework = request.form.get("homework", lead.homework)
    lead.send_retainer = 'send_retainer' in request.form
    lead.retainer_amount = request.form.get("retainer_amount") if lead.send_retainer else None
    lead.lvm = 'lvm' in request.form
    lead.not_pc = 'not_pc' in request.form
    lead.quote = request.form.get("quote")

    db.session.commit()

    # Prepare update email
    checkmark = lambda val: "✅" if val else "❌"
    msg = Message(f"Lead Updated: {lead.name}",
                  recipients=["attorneys@dischleylaw.com"],
                  sender=("New Lead", os.getenv('MAIL_DEFAULT_SENDER')))
    msg.body = f"""
Lead Updated:
Name: {lead.name}
Phone: {lead.phone}
Email: {lead.email}
Charge: {lead.charge}
Court Date: {lead.court_date}
Court Time: {lead.court_time}
Court: {lead.court}
Notes: {lead.notes}
Homework: {lead.homework}

Send Retainer: {checkmark(lead.send_retainer)} {f'(${lead.retainer_amount})' if lead.send_retainer else ''}
LVM: {checkmark(lead.lvm)}
Not a PC: {checkmark(lead.not_pc)}
Quote: ${lead.quote or 'N/A'}

View Lead: {url_for("view_lead", lead_id=lead.id, _external=True)}
    """
    mail.send(msg)

    # Optional: Send auto-email to client if LVM is checked and client email exists
    if lead.lvm and lead.email:
        auto_msg = Message("We Tried Reaching You", recipients=[lead.email])
        auto_msg.body = "We attempted to contact you regarding your recent inquiry. Please call us back at your earliest convenience."
        mail.send(auto_msg)

    return redirect(url_for("update_success"))

@app.route("/lead/<int:lead_id>/edit", methods=["GET", "POST"])
@login_required
def edit_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    if request.method == "POST":
        lead.name = request.form.get("name", lead.name)
        lead.phone = request.form.get("phone", lead.phone)
        lead.email = request.form.get("email", lead.email)
        lead.charge = request.form.get("charge", lead.charge)
        lead.court_date = request.form.get("court_date", lead.court_date)
        lead.notes = request.form.get("notes", lead.notes)
        db.session.commit()
        return redirect(url_for("dashboard"))
    return render_template("edit_lead.html", lead=lead)

@app.route("/case_result/<int:result_id>/edit", methods=["GET", "POST"])
@login_required
def edit_case_result(result_id):
    result = CaseResult.query.get_or_404(result_id)
    if request.method == "POST":
        result.defendant_name = request.form.get("defendant_name", result.defendant_name)
        result.offense = request.form.get("offense", result.offense)
        result.amended_charge = request.form.get("amended_charge", result.amended_charge)
        result.disposition = request.form.get("disposition", result.disposition)
        result.other_disposition = request.form.get("other_disposition", result.other_disposition)
        result.jail_time_imposed = request.form.get("jail_time_imposed", result.jail_time_imposed)
        result.jail_time_suspended = request.form.get("jail_time_suspended", result.jail_time_suspended)
        result.fine_imposed = request.form.get("fine_imposed", result.fine_imposed)
        result.fine_suspended = request.form.get("fine_suspended", result.fine_suspended)
        result.license_suspension = request.form.get("license_suspension", result.license_suspension)
        result.asap_ordered = request.form.get("asap_ordered", result.asap_ordered)
        result.probation_type = request.form.get("probation_type", result.probation_type)
        result.was_continued = request.form.get("was_continued", result.was_continued)
        result.continuation_date = request.form.get("continuation_date", result.continuation_date)
        result.notes = request.form.get("notes", result.notes)
        db.session.commit()
        return redirect(url_for("dashboard"))
    return render_template("edit_case_result.html", result=result)

@app.route("/update-success")
def update_success():
    return render_template("update_success.html")

@app.route("/case_result", methods=["GET", "POST"])
@login_required
def case_result():
    if request.method == "POST":
        data = request.form
        
        result = CaseResult(
            defendant_name=data.get("defendant_name"),
            offense=data.get("offense"),
            amended_charge=data.get("amended_charge"),
            disposition=data.get("disposition"),
            other_disposition=data.get("other_disposition"),
            jail_time_imposed=data.get("jail_time_imposed"),
            jail_time_suspended=data.get("jail_time_suspended"),
            fine_imposed=data.get("fine_imposed"),
            fine_suspended=data.get("fine_suspended"),
            license_suspension=data.get("license_suspension"),
            asap_ordered=data.get("asap_ordered"),
            probation_type=data.get("probation_type"),
            was_continued=data.get("was_continued"),
            continuation_date=data.get("continuation_date"),
            client_email=data.get("client_email"),
            notes=data.get("notes"),
            date_disposition=data.get("date_disposition"),
        )
        db.session.add(result)
        db.session.commit()

        msg_body = f"""
CASE RESULT

Defendant: {data.get("defendant_name")}
Court: {data.get("court")}
Original Charge: {data.get("offense")}
"""

        disposition = data.get("disposition")
        amended_charge = data.get("amended_charge")

        if disposition == "Guilty" and amended_charge and amended_charge != "None":
            msg_body += f"You were found guilty of an amended charge: {amended_charge}\n"
        elif disposition in ["Not Guilty", "Nolle Prosequi", "Dismissed", "Dismissed with costs"]:
            msg_body += f"Disposition: {disposition}\n"
        elif disposition == "Deferred Disposition":
            msg_body += f"Deferred Disposition of charge: {amended_charge or data.get('offense')}\n"


        if data.get("send_review_links"):
            msg_body += f"""

---

REVIEW REQUEST EMAIL

Dear {data.get("defendant_name")},

You were charged with {data.get("offense")}.
"""
            if disposition == "Guilty" and amended_charge and amended_charge != "None":
                msg_body += f"You were found guilty of the amended charge: {amended_charge}.\n"
            elif disposition in ["Not Guilty", "Nolle Prosequi"]:
                msg_body += f"You were found {disposition} of the charge.\n"
            elif disposition == "Deferred Disposition":
                msg_body += f"You received a deferred disposition.\n"
            msg_body += f"""
Thank you for choosing Dischley Law, PLLC. We truly appreciate the trust you placed in our firm and are delighted we could assist you with your legal matter. Your positive experience is our greatest reward, and your feedback helps others find trusted legal guidance.

We invite you to share your experience by leaving a review. You may choose to review our firm as a whole or share your thoughts specifically about our attorneys.

Firm Reviews:
• Google (Manassas Office): https://g.page/r/CcUBoz3y4zj5EB0/review
• Google (Fairfax Office): https://g.page/dischleylawfairfax/review
• Facebook: https://www.facebook.com/dischleylaw/reviews

David Dischley Reviews:
• Lawyers.com: https://www.lawyers.com/manassas/virginia/david-dischley-42907553-a/
• Justia: https://lawyers.justia.com/lawyer/david-joseph-dischley-1498182
• Avvo: https://www.avvo.com/attorneys/20110-va-david-dischley-1720133.html

Patrick O’Brien Reviews:
• Avvo: https://www.avvo.com/attorneys/22314-va-patrick-obrien-5090692/reviews.html
• Lawyers.com: https://www.lawyers.com/manassas/virginia/patrick-t-obrien-300385082-a/

Thank you again for your support and for taking the time to share your feedback. Your insights not only motivate our team but also help others in need of exceptional legal representation.
"""

        msg = Message(
            subject=f"Case Results - {data.get('defendant_name')}",
            recipients=["attorneys@dischleylaw.com"],
            sender=formataddr(("Case Result", os.getenv('MAIL_DEFAULT_SENDER')))
        )
        msg.body = msg_body
        mail.send(msg)

        return redirect(url_for("case_result_success"))
    return render_template("case_result.html")

@app.route("/case_result_success")
def case_result_success():
    return render_template("case_results_success.html")

def init_db():
    with app.app_context():
        db.create_all()

if __name__ == "__main__":
    init_db()
