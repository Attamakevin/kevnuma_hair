from flask import Flask, render_template, redirect, url_for, session, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_uploads import UploadSet, configure_uploads, IMAGES
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, TextAreaField, HiddenField, SelectField
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import InputRequired
import random
import stripe
from sqlalchemy import or_
# Application
app = Flask(__name__)

app.config['STRIPE_PUBLIC_KEY'] = 'pk_test_51NwAbDIcVse6hx5oGRQi3by0J0dYRSxueBE33ogRwZ5znJDqagrIYL1gfdVBCQJrM620PGJSWsU2iEaIssPm1RqI009V9BRmC8'
app.config['STRIPE_SECRET_KEY'] = 'sk_test_51NwAbDIcVse6hx5oZPSRTVhPIBXQbcrAdwrALxXQldutnVpqcRML8NLUKv2BXn33iANArUuKXPHalY8jyv5HhVFO00WtVsYQJH'

stripe.api_key = app.config['STRIPE_SECRET_KEY']
# Flask-Uploads setup
photos = UploadSet('photos', IMAGES)
app.config['UPLOADED_PHOTOS_DEST'] = 'images'

# SQLAlchemy and Flask-Migrate setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trendy.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'mysecret'
configure_uploads(app, photos)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Models
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    price = db.Column(db.Integer)  # in cents
    stock = db.Column(db.Integer)
    description = db.Column(db.String(500))
    image = db.Column(db.String(100))

    # Define a relationship with Order_Item
    orders = db.relationship('Order_Item', backref='product', lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(5))
    first_name = db.Column(db.String(20))
    last_name = db.Column(db.String(20))
    phone_number = db.Column(db.Integer)
    email = db.Column(db.String(50))
    address = db.Column(db.String(100))
    city = db.Column(db.String(100))
    state = db.Column(db.String(20))
    country = db.Column(db.String(20))
    status = db.Column(db.String(10))
    payment_type = db.Column(db.String(10))

    # Define a relationship with Order_Item
    items = db.relationship('Order_Item', backref='order', lazy=True)

    def order_total(self):
        total_cost = db.session.query(db.func.sum(
            Order_Item.quantity * Product.price)).join(Product).filter(
            Order_Item.order_id == self.id).scalar()
        if total_cost is not None:
            return int(total_cost) + 2500
        else:
            return 0.00  # Return 1000 if the query result is None




    def quantity_total(self):
        return db.session.query(db.func.sum(
            Order_Item.quantity)).filter(Order_Item.order_id == self.id).scalar()

class Order_Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(50))
    comment_text = db.Column(db.String(500))
    image = db.Column(db.String(100))
    #product_id = db.Column(db.Integer, db.ForeignKey('product.id'))

class AddComment(FlaskForm):
    customer_name = StringField('Your Name', validators=[InputRequired()])
    comment_text = TextAreaField('Your Comment', validators=[InputRequired()])
    image = FileField('Upload Image', validators=[FileAllowed(['jpg', 'png', 'jpeg'])])

# Flask-WTF Forms
class AddProduct(FlaskForm):
    name = StringField('Name')
    price = IntegerField('Price')
    stock = IntegerField('Stock')
    description = TextAreaField('Description')
    image = FileField(
        'Image', validators=[FileAllowed(IMAGES, 'Only images are accepted.')])

class AddToCart(FlaskForm):
    quantity = IntegerField('Quantity')
    id = HiddenField('ID')

class Checkout(FlaskForm):
    first_name = StringField('First Name')
    last_name = StringField('Last Name')
    phone_number = StringField('Number')
    email = StringField('Email')
    address = StringField('Address')
    city = StringField('City')
    state = SelectField('State',
                        choices=[('EN', 'Enugu'), ('ABJ', 'Abuja'),
                                 ('LA', 'Lagos')])
    country = SelectField('Country',
                          choices=[('NG', 'Nigeria'), ('UK', 'United Kingdom'),
                                   ('FRA', 'France')])
    payment_type = SelectField('Payment Type',
                               choices=[('CK', 'card Payment'),
                                        ('WT', 'Bank Transfer')],validators=[InputRequired()])

# Define a function to handle the cart
def handle_cart():
    products = []
    grand_total = 0
    index = 0
    quantity_total = 0

    for item in session['cart']:
        product = Product.query.filter_by(id=item['id']).first()

        quantity = int(item['quantity'])
        total = quantity * product.price
        grand_total += total
        quantity_total += quantity

        products.append({
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'image': product.image,
            'quantity': quantity,
            'total': total,
            'index': index
        })
        index += 1

    grand_total_plus_shipping = grand_total + 2500

    return products, grand_total, grand_total_plus_shipping, quantity_total

# Routes
@app.route('/')
def index():
    comment_form = AddComment()

    products = Product.query.all()
    #product = Product.query.filter_by(id=id).first()
    comments = Comment.query.all()
    return render_template('index.html', products=products, comment_form=comment_form, comments=comments)

# Add other routes and your app.run() statement here

    
@app.route('/product/<id>')
def product(id):
    product = Product.query.filter_by(id=id).first()

    form = AddToCart()

    return render_template('view-product.html', product=product, form=form)
@app.route('/search', methods=['GET', 'POST'])
def search():
    search_term = request.form.get('search_term', '')
    
    if request.method == 'POST' and search_term:
        products = Product.query.filter(or_(
            Product.name.ilike(f"%{search_term}%"),
            Product.description.ilike(f"%{search_term}%")
        )).all()
    else:
        products = Product.query.all()

    return render_template('search_view.html', products=products, search_term=search_term)
@app.route('/add-comment/', methods=['POST'])
def add_comment():
    form = AddComment()
    #product = Product.query.filter_by(id=id).first()
    if form.validate_on_submit():
        # Save the image and get the filename
        if form.image.data:
            filename = photos.save(form.image.data)
            image_url = url_for('uploaded_file', filename=filename)
            print("image saved successfully")
        else:
            image_url = None

        # Create a new comment
        comment = Comment(
            customer_name=form.customer_name.data,
            comment_text=form.comment_text.data,
            image=image_url,
            
        )

        db.session.add(comment)
        db.session.commit()

    return redirect(url_for('index',))

@app.route('/quick-add/<id>')
def quick_add(id):
  if 'cart' not in session:
    session['cart'] = []

  session['cart'].append({'id': id, 'quantity': 1})
  session.modified = True

  return redirect(url_for('index'))


@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
  if 'cart' not in session:
    session['cart'] = []

  form = AddToCart()

  if form.validate_on_submit():

    session['cart'].append({
        'id': form.id.data,
        'quantity': form.quantity.data
    })
    session.modified = True

  return redirect(url_for('index'))


@app.route('/cart')
def cart():
  products, grand_total, grand_total_plus_shipping, quantity_total = handle_cart(
  )

  return render_template('cart.html',
                         products=products,
                         grand_total=grand_total,
                         grand_total_plus_shipping=grand_total_plus_shipping,
                         quantity_total=quantity_total)


@app.route('/remove-from-cart/<index>')
def remove_from_cart(index):
  del session['cart'][int(index)]
  session.modified = True
  return redirect(url_for('cart'))


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
  form = Checkout()

  products, grand_total, grand_total_plus_shipping, quantity_total = handle_cart(
  )

  if form.validate_on_submit():

    order = Order()
    form.populate_obj(order)
    order.reference = ''.join([random.choice('ABCDE') for _ in range(5)])
    order.status = 'PENDING'

    for product in products:
      order_item = Order_Item(quantity=product['quantity'],
                              product_id=product['id'])
      order.items.append(order_item)

      product = Product.query.filter_by(id=product['id']).update(
          {'stock': Product.stock - product['quantity']})

    db.session.add(order)
    db.session.commit()

    session['cart'] = []
    session.modified = True

    return redirect(url_for('payment'))

  return render_template('checkout.html',
                         form=form,
                         grand_total=grand_total,
                         grand_total_plus_shipping=grand_total_plus_shipping,
                         quantity_total=quantity_total)
@app.route('/payment')
def payment():
    grand_total_plus_shipping=Order.order_total(Order)

    return render_template('payment.html',grand_total_plus_shipping=grand_total_plus_shipping)


@app.route('/admin')
def admin():
  products = Product.query.all()
  products_in_stock = Product.query.filter(Product.stock > 0).count()

  orders = Order.query.all()

  return render_template('admin/index.html',
                         admin=True,
                         products=products,
                         products_in_stock=products_in_stock,
                         orders=orders)

from flask import send_from_directory

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOADED_PHOTOS_DEST'], filename)

@app.route('/admin/add', methods=['GET', 'POST'])
def add():
    form = AddProduct()

    if form.validate_on_submit():
        if form.image.data:  # Check if an image file was provided
            filename = photos.save(form.image.data)  # Save the image and get the filename
            image_url = url_for('uploaded_file', filename=filename)  # Construct the image URL
        else:
            image_url = None

        new_product = Product(
            name=form.name.data,
            price=form.price.data,
            stock=form.stock.data,
            description=form.description.data,
            image=image_url
        )
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('admin'))

    return render_template('admin/add-product.html', admin=True, form=form)
@app.route('/admin/remove-product/<int:product_id>', methods=['POST'])
def admin_remove_product(product_id):
    product = Product.query.get(product_id)

    if product:
        db.session.delete(product)
        db.session.commit()
    else:
        abort(404)  # Product not found

    return redirect(url_for('admin'))
@app.route('/admin/order/<order_id>')
def order(order_id):
  order = Order.query.filter_by(id=int(order_id)).first()

  return render_template('admin/view-order.html', order=order, admin=True)

@app.route('/admin/remove-order/<int:order_id>', methods=['POST'])
def admin_remove_order(order_id):
    order = Order.query.get(order_id)

    if order and order.status == 'PENDING':
        db.session.delete(order)
        db.session.commit()
    else:
        abort(404)  # Order not found or not pending

    return redirect(url_for('admin'))


if __name__ == '__main__':
    app.run()
