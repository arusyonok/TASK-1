#TASK-1

from math import ceil
from flask import Flask, render_template, request
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)

# declaring db variables
client = MongoClient()
db = client['shopping']
catalog_collection = db['catalog'] # collection for the storage of the products
basket_collection = db['basket'] # collection for the storage of the shopping basket items

PER_PAGE = 3

ERROR_DEFAULT = "What are you trying to do? Try again"

# catalog listing of the available products with pagination
@app.route('/')
@app.route("/catalog/")
@app.route("/catalog/<current_page>/")
def main(current_page = 1):
    response = get_catalog(current_page=current_page)

    if response['catalog_items'] == False:
        return render_template("index.html", page_name="message", message=ERROR_DEFAULT)

    return render_template("index.html", page_name="catalog", total_pages=response['total_pages'], catalog_items=response['catalog_items'], path="/catalog/", current_page=int(current_page))

# catalog search based on the price range or keyword with pagination
@app.route("/catalog/search/")
@app.route("/catalog/search/<current_page>/")
def search_catalog(current_page = 1):
    response = get_catalog(current_page, request.args['price_min'], request.args['price_max'], request.args['search_word'])

    if response['catalog_items'] == False:
        return render_template("index.html", page_name="message", message=ERROR_DEFAULT)

    search_query = "?search_word=" + request.args['search_word'] + "&price_min=" + request.args['price_min'] + "&price_max=" + request.args['price_max']

    return render_template("index.html", page_name="catalog", total_pages=response['total_pages'], catalog_items=response['catalog_items'], path="/catalog/search/", search_query = search_query, current_page=int(current_page))

# get products from the db, based on price range, name, sorted by name, with pagination
def get_catalog(current_page = 1, price_min = False, price_max = False, search_word = ""):
    total_count = int(catalog_collection.count())
    catalog_items = []
    conditions = []
    condition_query = {}
    response = {}

    try:
        current_page = int(current_page)
    except:
        return False

    if current_page <= 0:
        current_page = 1

    first_item_index = PER_PAGE * current_page - PER_PAGE
    if first_item_index > total_count:
        first_item_index = 0

    if price_min and price_max:
        try:
            price_min = int(price_min)
            price_max = int(price_max)
            if price_min > price_max or price_min < 0 or price_max < 0:
                raise Exception()
        except:
            return False

        conditions.append({"price": {"$gte": price_min, "$lte": price_max}})

    conditions.append({"name": {"$regex": "^"+ str(search_word), "$options": "i"}})

    if len(conditions) != 0:
        condition_query = {"$and": conditions}

    total_pages = ceil(catalog_collection.find(condition_query).count() / PER_PAGE)
    cursor = catalog_collection.find(condition_query).skip(first_item_index).limit(PER_PAGE).sort("name", 1)

    for item in cursor:
        catalog_items.append(item)

    response = {'catalog_items': catalog_items, 'total_pages': total_pages}

    return response

# show adding product the catalog view and post to the catalog
@app.route("/product/add/", methods=["GET", "POST"])
def add_product():
    if request.method == "GET":
        return render_template("index.html", page_name="add_product")
    elif request.method == "POST":
        try:
            product_name = str(request.form['product_name'])

            if catalog_collection.find({"name": product_name}).count() > 0:
                raise Exception

            product_price = int(request.form['product_price'])
            product_qty = int(request.form['product_qty'])
            if product_qty < 1 or product_price < 0 or len(product_name) == 0:
                raise Exception
        except:
            return render_template("index.html", message=ERROR_DEFAULT, page_name="message")

        product = {"name": product_name, "price": product_price, "qty": product_qty}

        catalog_collection.insert(product)
        return render_template("index.html", message="Product added successfully", page_name="message")

# show product update view and update a product
@app.route("/product/edit/", methods=["POST"])
@app.route("/product/edit/<id>/", methods=["GET"])
def edit_product(id = 0):
    if request.method == "GET":
        try:
            id = ObjectId(id)
        except:
            return render_template("index.html", message=ERROR_DEFAULT, page_name="message")

        product_data = get_product_data(id)
        if product_data == False:
            return render_template("index.html", message="Couldn't find the item in the catalog", page_name="message")

        return render_template("index.html", page_name="update_product", product=product_data)
    elif request.method == "POST":
        try:
            product_name = str(request.form['product_name'])
            product_price = int(request.form['product_price'])
            product_qty = int(request.form['product_qty'])
            product_id = ObjectId(request.form['product_id'])
            if product_qty < 1 or product_price < 0 or len(product_name) == 0:
                raise Exception
        except:
            return render_template("index.html", message=ERROR_DEFAULT, page_name="message")

        new_product_data = {"name": product_name, "price": product_price, "qty": product_qty}

        row = catalog_collection.update({"_id": product_id}, new_product_data)
        if row['n'] == 0:
            return render_template("index.html", message="No product was updated", page_name="message")

        return render_template("index.html", message="Product updated successfully", page_name="message")

#show the basket
@app.route("/basket/")
def show_basket():
    basket_items = []
    cursor = basket_collection.find()
    for c in cursor:
        basket_items.append(c)

    return render_template("index.html", page_name="basket", basket_items=basket_items)

# show adding to the basket view and post to the basket
@app.route("/basket/add/", methods=['POST'])
@app.route("/basket/add/<product_id>/", methods=["GET"])
def add_to_basket(product_id = 0):
    if request.method == "GET":
        try:
            product_id = ObjectId(product_id)
            product_data = get_product_data(product_id)
            if product_data == False or product_in_basket(product_data['name']) == True:
                raise Exception
        except:
            return render_template("index.html", message=ERROR_DEFAULT, page_name="message")

        return render_template("index.html", page_name="add_to_basket", product = product_data)
    elif request.method == "POST":
        try:
            product_id = ObjectId(request.form['product_id'])
            basket_qty = int(request.form['basket_qty'])
            product_data = get_product_data(product_id)
            if basket_qty <= 0 or product_data == False or product_data['qty'] < basket_qty:
                raise Exception
        except:
            return render_template("index.html", message=ERROR_DEFAULT, page_name="message")

        basket_collection.insert({'name': product_data['name'], 'qty': basket_qty})
        catalog_collection.update({'name': product_data['name']}, {'$inc': {"qty": -basket_qty}})

        return render_template("index.html", message="Product added to the basket successfully", page_name="message")

# show basket item update view and update a basket item
@app.route("/basket/edit/", methods=["POST"])
@app.route("/basket/edit/<basket_id>/", methods=["GET"])
def edit_basket_item(basket_id = 0):
    if request.method == "GET":
        try:
            basket_id = ObjectId(basket_id)
            basket = get_basket_data(basket_id)
            if basket == False:
                raise Exception
        except:
            return render_template("index.html", message=ERROR_DEFAULT, page_name="message")

        return render_template("index.html", page_name="update_basket", basket=basket)
    elif request.method == "POST":
        try:
            basket_qty = int(request.form['basket_qty'])
            basket_id = ObjectId(request.form['basket_id'])
            basket_data = get_basket_data(basket_id)
            if basket_qty == 0 or basket_qty < 1 or basket_qty > basket_data['qty'] or basket_data == False or basket_data['name'] == 0 :
                raise Exception
        except:
            return render_template("index.html", message=ERROR_DEFAULT, page_name="message")

        difference = int(basket_data['qty']) - basket_qty


        try:
            row = basket_collection.update({"_id": basket_id}, {'name': basket_data['name'], "qty": basket_qty})
            if row['n'] == 0:
                raise Exception

            cat_row = catalog_collection.update({'name': basket_data['name']}, {'$inc': {"qty": +difference}})

            if cat_row['n'] == 0:
                raise Exception

        except Exception:
            return render_template("index.html", message="Couldn't update the basket item quantity", page_name="message")

        return render_template("index.html", message="Basket item updated successfully", page_name="message")

# remove item from catalog or basket
@app.route("/product/delete/<id>/", defaults={'collection': catalog_collection})
@app.route("/basket/delete/<id>/", defaults={'collection': basket_collection})
def remove_item(id = 0, collection = 0):
    try:
        id = ObjectId(id)
        if collection == 0:
            raise Exception
    except:
        return render_template("index.html", message=ERROR_DEFAULT, page_name="message")

    row = collection.delete_one({"_id": id})

    if row.deleted_count == 0:
        return render_template("index.html", message="Couldn't delete it. Try again", page_name="message")

    return render_template("index.html", message="Deletion done successfully", page_name="message")

# get basket data by id
def get_basket_data(id):
    data = basket_collection.find({"_id": ObjectId(id)})
    if data.count() == 0:
        return False

    return data[0]

# get product data by id
def get_product_data(id):
    data = catalog_collection.find({"_id": ObjectId(id)})
    if data.count() == 0:
        return False

    return data[0]

# check if product is already in the basket
def product_in_basket(product_name):
    if basket_collection.find({"name": str(product_name)}).count() == 1:
        return True

    return False

# initialise data to the db
def initialise_db():
    if catalog_collection.count() != 0:
        return True

    catalog_items = [
        {"name": "apples", "price": 5, "qty": 10},
        {"name": "pears", "price": 10, "qty": 12},
        {"name": "grapes", "price": 7, "qty": 4},
        {"name": "oranges", "price": 9, "qty": 12},
        {"name": "apricots", "price": 3, "qty": 47},
        {"name": "eggplant", "price": 13, "qty": 10},
        {"name": "cheese", "price": 14, "qty": 14},
        {"name": "milk", "price": 11, "qty": 23},
        {"name": "avocado", "price": 43, "qty": 10},
        {"name": "tomatoes", "price": 10, "qty": 43},
        {"name": "eggs", "price": 5, "qty": 54},
        {"name": "ananas", "price": 23, "qty": 10},
        {"name": "eggplants", "price": 13, "qty": 10},
    ]

    catalog_collection.insert_many(catalog_items)


if __name__ == '__main__':
    initialise_db()
    app.run()