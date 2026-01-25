"""
Khana Management System - Flask Backend
Converted from Express.js to Flask
"""

import os
import re
import random
import json
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_pymongo import PyMongo
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
app.config['MONGO_URI'] = os.getenv('MONGO_URI', 'mongodb://localhost:27017/kms')
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET', 'your-secret-key')
JWT_EXPIRE_HOURS = int(os.getenv('JWT_EXPIRE_HOURS', 24))

# Initialize MongoDB
mongo = PyMongo(app)

# ==================== HELPER FUNCTIONS ====================

def json_response(data, status=200):
    """Helper to create JSON response with proper ObjectId handling"""
    return jsonify(convert_objectid(data)), status

def convert_objectid(obj):
    """Recursively convert ObjectId to string in dicts/lists"""
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: convert_objectid(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectid(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj

def generate_token(user_id):
    """Generate JWT token"""
    payload = {
        'id': str(user_id),
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def generate_pickup_code():
    """Generate 6-digit pickup code"""
    return str(random.randint(100000, 999999))

def validate_email(email):
    """Validate email format"""
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w{2,3}$'
    return re.match(pattern, email) is not None

# ==================== MIDDLEWARE ====================

def protect(f):
    """JWT authentication middleware"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        if not token:
            return json_response({
                'success': False,
                'message': 'Not authorized to access this route'
            }, 401)
        
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user = mongo.db.users.find_one({'_id': ObjectId(payload['id'])})
            
            if not user:
                return json_response({
                    'success': False,
                    'message': 'User not found'
                }, 401)
            
            g.user = user
            print(f"🔐 Auth middleware - User: id={user['_id']}, role={user['role']}, canteenId={user.get('canteenId')}")
            
        except jwt.ExpiredSignatureError:
            return json_response({
                'success': False,
                'message': 'Token has expired'
            }, 401)
        except jwt.InvalidTokenError:
            return json_response({
                'success': False,
                'message': 'Not authorized to access this route'
            }, 401)
        
        return f(*args, **kwargs)
    return decorated_function

def authorize(*roles):
    """Role authorization decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if g.user['role'] not in roles:
                return json_response({
                    'success': False,
                    'message': f"User role {g.user['role']} is not authorized to access this route"
                }, 403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==================== REQUEST LOGGING MIDDLEWARE ====================

@app.before_request
def log_request():
    """Log incoming requests"""
    request_id = datetime.now().isoformat()
    print(f"\n[{request_id}] ─────────────────────────────────────────")
    print(f"📥 {request.method} {request.path}")
    print(f"🔗 Full URL: {request.method} {request.url}")
    
    if request.args:
        print(f"📋 Query Params: {dict(request.args)}")
    
    if request.is_json and request.json:
        body_to_log = dict(request.json)
        if 'password' in body_to_log:
            body_to_log['password'] = '***hidden***'
        print(f"📤 Request Body: {json.dumps(body_to_log, indent=2)}")
    
    auth_header = request.headers.get('Authorization')
    if auth_header:
        print(f"🔐 Authorization: {auth_header[:30]}...")

# ==================== ROOT ROUTES ====================

@app.route('/')
def root():
    """Root route"""
    return json_response({
        'success': True,
        'message': 'Welcome to Khana Management System API (Flask)',
        'version': '1.0.0',
        'endpoints': {
            'auth': '/api/auth',
            'canteens': '/api/canteens',
            'menu': '/api/menu',
            'orders': '/api/orders',
            'payments': '/api/payments'
        }
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return json_response({
        'success': True,
        'message': 'KMS Backend (Flask) is running',
        'timestamp': datetime.now().isoformat()
    })

# ==================== AUTH ROUTES ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user (Students only)"""
    data = request.get_json()
    
    # Validation
    errors = []
    if not data.get('name'):
        errors.append({'msg': 'Name is required', 'param': 'name'})
    if not data.get('email') or not validate_email(data.get('email', '')):
        errors.append({'msg': 'Please provide a valid email', 'param': 'email'})
    if not data.get('password') or len(data.get('password', '')) < 6:
        errors.append({'msg': 'Password must be at least 6 characters', 'param': 'password'})
    if data.get('role') not in ['STUDENT']:
        errors.append({'msg': 'Invalid role', 'param': 'role'})
    
    if errors:
        print(f"❌ Validation errors: {errors}")
        return json_response({'success': False, 'errors': errors}, 400)
    
    # Only STUDENT can self-register
    if data.get('role') != 'STUDENT':
        return json_response({
            'success': False,
            'message': 'Only students can register. Contact an administrator for other roles.'
        }, 400)
    
    print(f"📝 Register request: name={data['name']}, email={data['email']}, role={data['role']}")
    
    # Check if user exists
    if mongo.db.users.find_one({'email': data['email'].lower()}):
        print(f"❌ User already exists: {data['email']}")
        return json_response({
            'success': False,
            'message': 'User already exists'
        }, 400)
    
    try:
        # Create user
        user_data = {
            'name': data['name'].strip(),
            'email': data['email'].lower().strip(),
            'password': generate_password_hash(data['password']),
            'role': data['role'],
            'canteenId': None,
            'createdAt': datetime.utcnow()
        }
        
        result = mongo.db.users.insert_one(user_data)
        user_id = result.inserted_id
        
        token = generate_token(user_id)
        
        print(f"✅ User registered successfully: {user_id} Role: {data['role']}")
        
        return json_response({
            'success': True,
            'data': {
                '_id': str(user_id),
                'name': user_data['name'],
                'email': user_data['email'],
                'role': user_data['role'],
                'token': token
            }
        }, 201)
        
    except Exception as e:
        print(f"❌ Registration error: {str(e)}")
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    data = request.get_json()
    
    # Validation
    errors = []
    if not data.get('email') or not validate_email(data.get('email', '')):
        errors.append({'msg': 'Please provide a valid email', 'param': 'email'})
    if not data.get('password'):
        errors.append({'msg': 'Password is required', 'param': 'password'})
    
    if errors:
        return json_response({'success': False, 'errors': errors}, 400)
    
    try:
        # Find user
        user = mongo.db.users.find_one({'email': data['email'].lower()})
        
        if not user:
            return json_response({
                'success': False,
                'message': 'Invalid credentials'
            }, 401)
        
        # Check password
        if not check_password_hash(user['password'], data['password']):
            return json_response({
                'success': False,
                'message': 'Invalid credentials'
            }, 401)
        
        token = generate_token(user['_id'])
        
        return json_response({
            'success': True,
            'data': {
                '_id': str(user['_id']),
                'name': user['name'],
                'email': user['email'],
                'role': user['role'],
                'canteenId': str(user['canteenId']) if user.get('canteenId') else None,
                'token': token
            }
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/auth/me', methods=['GET'])
@protect
def get_me():
    """Get current user"""
    try:
        user = mongo.db.users.find_one({'_id': g.user['_id']})
        user_data = {k: v for k, v in user.items() if k != 'password'}
        
        return json_response({
            'success': True,
            'data': user_data
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/auth/profile', methods=['PUT'])
@protect
def update_profile():
    """Update user profile"""
    data = request.get_json()
    
    # Validation
    if data.get('name') is not None and not data.get('name'):
        return json_response({
            'success': False,
            'errors': [{'msg': 'Name cannot be empty', 'param': 'name'}]
        }, 400)
    
    try:
        user = mongo.db.users.find_one({'_id': g.user['_id']})
        
        if not user:
            return json_response({
                'success': False,
                'message': 'User not found'
            }, 404)
        
        # Update only allowed fields
        update_data = {}
        if data.get('name'):
            update_data['name'] = data['name'].strip()
        
        if update_data:
            mongo.db.users.update_one({'_id': g.user['_id']}, {'$set': update_data})
        
        updated_user = mongo.db.users.find_one({'_id': g.user['_id']})
        
        return json_response({
            'success': True,
            'data': {
                '_id': str(updated_user['_id']),
                'name': updated_user['name'],
                'email': updated_user['email'],
                'role': updated_user['role'],
                'canteenId': str(updated_user['canteenId']) if updated_user.get('canteenId') else None
            }
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/auth/password', methods=['PUT'])
@protect
def change_password():
    """Change password"""
    data = request.get_json()
    
    # Validation
    errors = []
    if not data.get('currentPassword'):
        errors.append({'msg': 'Current password is required', 'param': 'currentPassword'})
    if not data.get('newPassword') or len(data.get('newPassword', '')) < 6:
        errors.append({'msg': 'New password must be at least 6 characters', 'param': 'newPassword'})
    
    if errors:
        return json_response({'success': False, 'errors': errors}, 400)
    
    try:
        user = mongo.db.users.find_one({'_id': g.user['_id']})
        
        if not user:
            return json_response({
                'success': False,
                'message': 'User not found'
            }, 404)
        
        # Verify current password
        if not check_password_hash(user['password'], data['currentPassword']):
            return json_response({
                'success': False,
                'message': 'Current password is incorrect'
            }, 401)
        
        # Update password
        new_password_hash = generate_password_hash(data['newPassword'])
        mongo.db.users.update_one(
            {'_id': g.user['_id']},
            {'$set': {'password': new_password_hash}}
        )
        
        return json_response({
            'success': True,
            'message': 'Password updated successfully'
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

# ==================== CANTEEN ROUTES ====================

@app.route('/api/canteens', methods=['GET'])
def get_canteens():
    """Get all canteens"""
    try:
        canteens = list(mongo.db.canteens.find())
        
        return json_response({
            'success': True,
            'count': len(canteens),
            'data': canteens
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/canteens/<canteen_id>', methods=['GET'])
def get_canteen(canteen_id):
    """Get single canteen"""
    try:
        canteen = mongo.db.canteens.find_one({'_id': ObjectId(canteen_id)})
        
        if not canteen:
            return json_response({
                'success': False,
                'message': 'Canteen not found'
            }, 404)
        
        return json_response({
            'success': True,
            'data': canteen
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/canteens', methods=['POST'])
@protect
@authorize('ADMIN')
def create_canteen():
    """Create new canteen (Admin only)"""
    data = request.get_json()
    
    try:
        # Create the canteen
        canteen_data = {
            'name': data.get('name', '').strip(),
            'location': data.get('location', '').strip(),
            'isOpen': data.get('isOpen', False),
            'isOnlineOrdersEnabled': data.get('isOnlineOrdersEnabled', False),
            'maxBulkSize': data.get('maxBulkSize', 50),
            'description': data.get('description', ''),
            'imageUrl': data.get('imageUrl', ''),
            'createdAt': datetime.utcnow()
        }
        
        result = mongo.db.canteens.insert_one(canteen_data)
        canteen_id = result.inserted_id
        
        # Generate default credentials
        canteen_email = f"{data['name'].lower().replace(' ', '')}@kms.com"
        default_password = 'canteen123'
        
        # Create canteen user
        canteen_user_data = {
            'name': f"{data['name']} Staff",
            'email': canteen_email,
            'password': generate_password_hash(default_password),
            'role': 'CANTEEN',
            'canteenId': canteen_id,
            'createdAt': datetime.utcnow()
        }
        
        mongo.db.users.insert_one(canteen_user_data)
        
        canteen_data['_id'] = canteen_id
        
        return json_response({
            'success': True,
            'data': canteen_data,
            'credentials': {
                'email': canteen_email,
                'password': default_password,
                'canteenId': str(canteen_id)
            }
        }, 201)
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/canteens/<canteen_id>', methods=['PUT'])
@protect
@authorize('ADMIN', 'CANTEEN')
def update_canteen(canteen_id):
    """Update canteen"""
    data = request.get_json()
    
    try:
        canteen = mongo.db.canteens.find_one({'_id': ObjectId(canteen_id)})
        
        if not canteen:
            return json_response({
                'success': False,
                'message': 'Canteen not found'
            }, 404)
        
        # Check if user is canteen owner
        if g.user['role'] == 'CANTEEN' and str(g.user.get('canteenId')) != canteen_id:
            return json_response({
                'success': False,
                'message': 'Not authorized to update this canteen'
            }, 403)
        
        # Update canteen
        update_data = {k: v for k, v in data.items() if k not in ['_id', 'createdAt']}
        
        mongo.db.canteens.update_one(
            {'_id': ObjectId(canteen_id)},
            {'$set': update_data}
        )
        
        updated_canteen = mongo.db.canteens.find_one({'_id': ObjectId(canteen_id)})
        
        return json_response({
            'success': True,
            'data': updated_canteen
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/canteens/<canteen_id>/toggle-open', methods=['POST'])
@protect
@authorize('CANTEEN', 'ADMIN')
def toggle_canteen_open(canteen_id):
    """Toggle canteen open/close status"""
    try:
        print(f"🔄 Toggle open request: requestedCanteenId={canteen_id}, userRole={g.user['role']}, userCanteenId={g.user.get('canteenId')}")
        
        canteen = mongo.db.canteens.find_one({'_id': ObjectId(canteen_id)})
        
        if not canteen:
            return json_response({
                'success': False,
                'message': 'Canteen not found'
            }, 404)
        
        # Check if user is canteen owner
        if g.user['role'] == 'CANTEEN' and str(g.user.get('canteenId')) != canteen_id:
            print('❌ Authorization failed - canteenId mismatch')
            return json_response({
                'success': False,
                'message': 'Not authorized to update this canteen'
            }, 403)
        
        new_status = not canteen.get('isOpen', False)
        mongo.db.canteens.update_one(
            {'_id': ObjectId(canteen_id)},
            {'$set': {'isOpen': new_status}}
        )
        
        updated_canteen = mongo.db.canteens.find_one({'_id': ObjectId(canteen_id)})
        
        return json_response({
            'success': True,
            'data': updated_canteen
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/canteens/<canteen_id>/toggle-online-orders', methods=['POST'])
@protect
@authorize('CANTEEN', 'ADMIN')
def toggle_online_orders(canteen_id):
    """Toggle online orders enabled/disabled"""
    try:
        canteen = mongo.db.canteens.find_one({'_id': ObjectId(canteen_id)})
        
        if not canteen:
            return json_response({
                'success': False,
                'message': 'Canteen not found'
            }, 404)
        
        # Check if user is canteen owner
        if g.user['role'] == 'CANTEEN' and str(g.user.get('canteenId')) != canteen_id:
            return json_response({
                'success': False,
                'message': 'Not authorized to update this canteen'
            }, 403)
        
        new_status = not canteen.get('isOnlineOrdersEnabled', False)
        mongo.db.canteens.update_one(
            {'_id': ObjectId(canteen_id)},
            {'$set': {'isOnlineOrdersEnabled': new_status}}
        )
        
        updated_canteen = mongo.db.canteens.find_one({'_id': ObjectId(canteen_id)})
        
        return json_response({
            'success': True,
            'data': updated_canteen
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/canteens/<canteen_id>', methods=['DELETE'])
@protect
@authorize('ADMIN')
def delete_canteen(canteen_id):
    """Delete canteen (Admin only)"""
    try:
        canteen = mongo.db.canteens.find_one({'_id': ObjectId(canteen_id)})
        
        if not canteen:
            return json_response({
                'success': False,
                'message': 'Canteen not found'
            }, 404)
        
        mongo.db.canteens.delete_one({'_id': ObjectId(canteen_id)})
        
        return json_response({
            'success': True,
            'data': {}
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

# ==================== MENU ROUTES ====================

@app.route('/api/menu/canteen/<canteen_id>', methods=['GET'])
def get_canteen_menu(canteen_id):
    """Get menu for a canteen"""
    try:
        menu_items = list(mongo.db.menuitems.find({'canteenId': ObjectId(canteen_id)}))
        
        return json_response({
            'success': True,
            'count': len(menu_items),
            'data': menu_items
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/menu/<item_id>', methods=['GET'])
def get_menu_item(item_id):
    """Get single menu item"""
    try:
        menu_item = mongo.db.menuitems.find_one({'_id': ObjectId(item_id)})
        
        if not menu_item:
            return json_response({
                'success': False,
                'message': 'Menu item not found'
            }, 404)
        
        return json_response({
            'success': True,
            'data': menu_item
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/menu', methods=['POST'])
@protect
@authorize('CANTEEN', 'ADMIN')
def create_menu_item():
    """Create new menu item"""
    data = request.get_json()
    canteen_id = data.get('canteenId')
    
    print(f"➕ Create menu item request: requestedCanteenId={canteen_id}, userRole={g.user['role']}, userCanteenId={g.user.get('canteenId')}")
    
    try:
        # Verify canteen exists
        canteen = mongo.db.canteens.find_one({'_id': ObjectId(canteen_id)})
        
        if not canteen:
            return json_response({
                'success': False,
                'message': 'Canteen not found'
            }, 404)
        
        # Check if user is canteen owner
        if g.user['role'] == 'CANTEEN' and str(g.user.get('canteenId')) != canteen_id:
            print('❌ Authorization failed - canteenId mismatch for menu creation')
            return json_response({
                'success': False,
                'message': 'Not authorized to add items to this canteen'
            }, 403)
        
        menu_item_data = {
            'canteenId': ObjectId(canteen_id),
            'name': data.get('name', '').strip(),
            'description': data.get('description', ''),
            'price': float(data.get('price', 0)),
            'category': data.get('category', 'Snacks'),
            'isAvailable': data.get('isAvailable', True),
            'imageUrl': data.get('imageUrl', ''),
            'isVeg': data.get('isVeg', True),
            'createdAt': datetime.utcnow()
        }
        
        result = mongo.db.menuitems.insert_one(menu_item_data)
        menu_item_data['_id'] = result.inserted_id
        
        return json_response({
            'success': True,
            'data': menu_item_data
        }, 201)
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/menu/<item_id>', methods=['PUT'])
@protect
@authorize('CANTEEN', 'ADMIN')
def update_menu_item(item_id):
    """Update menu item"""
    data = request.get_json()
    
    try:
        menu_item = mongo.db.menuitems.find_one({'_id': ObjectId(item_id)})
        
        if not menu_item:
            return json_response({
                'success': False,
                'message': 'Menu item not found'
            }, 404)
        
        # Check if user is canteen owner
        if g.user['role'] == 'CANTEEN' and str(g.user.get('canteenId')) != str(menu_item['canteenId']):
            return json_response({
                'success': False,
                'message': 'Not authorized to update this menu item'
            }, 403)
        
        # Update menu item
        update_data = {k: v for k, v in data.items() if k not in ['_id', 'canteenId', 'createdAt']}
        
        mongo.db.menuitems.update_one(
            {'_id': ObjectId(item_id)},
            {'$set': update_data}
        )
        
        updated_item = mongo.db.menuitems.find_one({'_id': ObjectId(item_id)})
        
        return json_response({
            'success': True,
            'data': updated_item
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/menu/<item_id>/toggle-availability', methods=['PATCH'])
@protect
@authorize('CANTEEN', 'ADMIN')
def toggle_menu_availability(item_id):
    """Toggle menu item availability"""
    try:
        menu_item = mongo.db.menuitems.find_one({'_id': ObjectId(item_id)})
        
        if not menu_item:
            return json_response({
                'success': False,
                'message': 'Menu item not found'
            }, 404)
        
        # Check if user is canteen owner
        if g.user['role'] == 'CANTEEN' and str(g.user.get('canteenId')) != str(menu_item['canteenId']):
            return json_response({
                'success': False,
                'message': 'Not authorized to update this menu item'
            }, 403)
        
        new_status = not menu_item.get('isAvailable', True)
        mongo.db.menuitems.update_one(
            {'_id': ObjectId(item_id)},
            {'$set': {'isAvailable': new_status}}
        )
        
        updated_item = mongo.db.menuitems.find_one({'_id': ObjectId(item_id)})
        
        return json_response({
            'success': True,
            'data': updated_item
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/menu/<item_id>', methods=['DELETE'])
@protect
@authorize('CANTEEN', 'ADMIN')
def delete_menu_item(item_id):
    """Delete menu item"""
    try:
        menu_item = mongo.db.menuitems.find_one({'_id': ObjectId(item_id)})
        
        if not menu_item:
            return json_response({
                'success': False,
                'message': 'Menu item not found'
            }, 404)
        
        # Check if user is canteen owner
        if g.user['role'] == 'CANTEEN' and str(g.user.get('canteenId')) != str(menu_item['canteenId']):
            return json_response({
                'success': False,
                'message': 'Not authorized to delete this menu item'
            }, 403)
        
        mongo.db.menuitems.delete_one({'_id': ObjectId(item_id)})
        
        return json_response({
            'success': True,
            'data': {}
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

# ==================== ORDER ROUTES ====================

@app.route('/api/orders', methods=['POST'])
@protect
def create_order():
    """Create new order"""
    data = request.get_json()
    canteen_id = data.get('canteenId')
    items = data.get('items', [])
    special_instructions = data.get('specialInstructions', '')
    
    try:
        # Verify canteen exists and is open
        canteen = mongo.db.canteens.find_one({'_id': ObjectId(canteen_id)})
        
        if not canteen:
            return json_response({
                'success': False,
                'message': 'Canteen not found'
            }, 404)
        
        if not canteen.get('isOpen'):
            return json_response({
                'success': False,
                'message': 'Canteen is currently closed'
            }, 400)
        
        if not canteen.get('isOnlineOrdersEnabled'):
            return json_response({
                'success': False,
                'message': 'Online orders are currently disabled for this canteen'
            }, 400)
        
        # Calculate total and validate items
        total_amount = 0
        total_quantity = 0
        order_items = []
        
        for item in items:
            menu_item = mongo.db.menuitems.find_one({'_id': ObjectId(item['menuItem'])})
            
            if not menu_item:
                return json_response({
                    'success': False,
                    'message': f"Menu item {item['menuItem']} not found"
                }, 404)
            
            if not menu_item.get('isAvailable', True):
                return json_response({
                    'success': False,
                    'message': f"{menu_item['name']} is currently unavailable"
                }, 400)
            
            if str(menu_item['canteenId']) != canteen_id:
                return json_response({
                    'success': False,
                    'message': f"{menu_item['name']} does not belong to this canteen"
                }, 400)
            
            item_total = menu_item['price'] * item['quantity']
            total_amount += item_total
            total_quantity += item['quantity']
            
            order_items.append({
                'menuItem': menu_item['_id'],
                'name': menu_item['name'],
                'price': menu_item['price'],
                'quantity': item['quantity'],
                'isVeg': menu_item.get('isVeg', True)
            })
        
        # Check if bulk order
        is_bulk_order = total_quantity > canteen.get('maxBulkSize', 50)
        
        # Create order
        order_data = {
            'userId': g.user['_id'],
            'canteenId': ObjectId(canteen_id),
            'items': order_items,
            'totalAmount': total_amount,
            'isBulkOrder': is_bulk_order,
            'specialInstructions': special_instructions,
            'status': 'CREATED',
            'pickupCode': None,
            'pickupCodeUsed': False,
            'createdAt': datetime.utcnow(),
            'updatedAt': datetime.utcnow()
        }
        
        result = mongo.db.orders.insert_one(order_data)
        order_data['_id'] = result.inserted_id
        
        return json_response({
            'success': True,
            'data': order_data
        }, 201)
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/orders/my', methods=['GET'])
@protect
def get_my_orders():
    """Get current user's orders"""
    try:
        pipeline = [
            {'$match': {'userId': g.user['_id']}},
            {'$sort': {'createdAt': -1}},
            {'$lookup': {
                'from': 'canteens',
                'localField': 'canteenId',
                'foreignField': '_id',
                'as': 'canteenInfo'
            }},
            {'$addFields': {
                'canteenId': {
                    '$cond': {
                        'if': {'$gt': [{'$size': '$canteenInfo'}, 0]},
                        'then': {
                            '_id': {'$arrayElemAt': ['$canteenInfo._id', 0]},
                            'name': {'$arrayElemAt': ['$canteenInfo.name', 0]},
                            'location': {'$arrayElemAt': ['$canteenInfo.location', 0]}
                        },
                        'else': '$canteenId'
                    }
                }
            }},
            {'$project': {'canteenInfo': 0}}
        ]
        
        orders = list(mongo.db.orders.aggregate(pipeline))
        
        return json_response({
            'success': True,
            'count': len(orders),
            'data': orders
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/orders/all', methods=['GET'])
@protect
@authorize('ADMIN')
def get_all_orders():
    """Get all orders (Admin only)"""
    try:
        status = request.args.get('status')
        query = {}
        if status:
            query['status'] = status
        
        pipeline = [
            {'$match': query},
            {'$sort': {'createdAt': -1}},
            {'$lookup': {
                'from': 'users',
                'localField': 'userId',
                'foreignField': '_id',
                'as': 'userInfo'
            }},
            {'$lookup': {
                'from': 'canteens',
                'localField': 'canteenId',
                'foreignField': '_id',
                'as': 'canteenInfo'
            }},
            {'$addFields': {
                'userId': {
                    '$cond': {
                        'if': {'$gt': [{'$size': '$userInfo'}, 0]},
                        'then': {
                            '_id': {'$arrayElemAt': ['$userInfo._id', 0]},
                            'name': {'$arrayElemAt': ['$userInfo.name', 0]},
                            'email': {'$arrayElemAt': ['$userInfo.email', 0]}
                        },
                        'else': '$userId'
                    }
                },
                'canteenId': {
                    '$cond': {
                        'if': {'$gt': [{'$size': '$canteenInfo'}, 0]},
                        'then': {
                            '_id': {'$arrayElemAt': ['$canteenInfo._id', 0]},
                            'name': {'$arrayElemAt': ['$canteenInfo.name', 0]},
                            'location': {'$arrayElemAt': ['$canteenInfo.location', 0]}
                        },
                        'else': '$canteenId'
                    }
                }
            }},
            {'$project': {'userInfo': 0, 'canteenInfo': 0}}
        ]
        
        orders = list(mongo.db.orders.aggregate(pipeline))
        
        return json_response({
            'success': True,
            'count': len(orders),
            'data': orders
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/orders/canteen/<canteen_id>', methods=['GET'])
@protect
@authorize('CANTEEN', 'ADMIN')
def get_canteen_orders(canteen_id):
    """Get orders for a canteen"""
    try:
        # Check if user is canteen owner
        if g.user['role'] == 'CANTEEN' and str(g.user.get('canteenId')) != canteen_id:
            return json_response({
                'success': False,
                'message': 'Not authorized to view orders for this canteen'
            }, 403)
        
        status = request.args.get('status')
        query = {'canteenId': ObjectId(canteen_id)}
        
        # Only show paid orders to canteen
        if status:
            query['status'] = status
        else:
            query['status'] = {'$in': ['PAID', 'ACCEPTED', 'PREPARING', 'READY']}
        
        pipeline = [
            {'$match': query},
            {'$sort': {'createdAt': -1}},
            {'$lookup': {
                'from': 'users',
                'localField': 'userId',
                'foreignField': '_id',
                'as': 'userInfo'
            }},
            {'$addFields': {
                'userId': {
                    '$cond': {
                        'if': {'$gt': [{'$size': '$userInfo'}, 0]},
                        'then': {
                            '_id': {'$arrayElemAt': ['$userInfo._id', 0]},
                            'name': {'$arrayElemAt': ['$userInfo.name', 0]},
                            'email': {'$arrayElemAt': ['$userInfo.email', 0]}
                        },
                        'else': '$userId'
                    }
                }
            }},
            {'$project': {'userInfo': 0}}
        ]
        
        orders = list(mongo.db.orders.aggregate(pipeline))
        
        return json_response({
            'success': True,
            'count': len(orders),
            'data': orders
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/orders/canteen/<canteen_id>/completed', methods=['GET'])
@protect
@authorize('CANTEEN', 'ADMIN')
def get_canteen_completed_orders(canteen_id):
    """Get completed orders for a canteen with earnings statistics"""
    try:
        # Check if user is canteen owner
        if g.user['role'] == 'CANTEEN' and str(g.user.get('canteenId')) != canteen_id:
            return json_response({
                'success': False,
                'message': 'Not authorized to view orders for this canteen'
            }, 403)
        
        # Fetch all completed orders
        pipeline = [
            {'$match': {'canteenId': ObjectId(canteen_id), 'status': 'COMPLETED'}},
            {'$sort': {'createdAt': -1}},
            {'$lookup': {
                'from': 'users',
                'localField': 'userId',
                'foreignField': '_id',
                'as': 'userInfo'
            }},
            {'$addFields': {
                'userId': {
                    '$cond': {
                        'if': {'$gt': [{'$size': '$userInfo'}, 0]},
                        'then': {
                            '_id': {'$arrayElemAt': ['$userInfo._id', 0]},
                            'name': {'$arrayElemAt': ['$userInfo.name', 0]},
                            'email': {'$arrayElemAt': ['$userInfo.email', 0]}
                        },
                        'else': '$userId'
                    }
                }
            }},
            {'$project': {'userInfo': 0}}
        ]
        
        completed_orders = list(mongo.db.orders.aggregate(pipeline))
        
        # Calculate earnings for today
        start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
        
        daily_earnings_pipeline = [
            {
                '$match': {
                    'canteenId': ObjectId(canteen_id),
                    'status': 'COMPLETED',
                    'updatedAt': {'$gte': start_of_day, '$lte': end_of_day}
                }
            },
            {
                '$group': {
                    '_id': None,
                    'total': {'$sum': '$totalAmount'}
                }
            }
        ]
        
        daily_result = list(mongo.db.orders.aggregate(daily_earnings_pipeline))
        daily_earnings = daily_result[0]['total'] if daily_result else 0
        
        # Calculate earnings for current month
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        monthly_earnings_pipeline = [
            {
                '$match': {
                    'canteenId': ObjectId(canteen_id),
                    'status': 'COMPLETED',
                    'updatedAt': {'$gte': start_of_month}
                }
            },
            {
                '$group': {
                    '_id': None,
                    'total': {'$sum': '$totalAmount'}
                }
            }
        ]
        
        monthly_result = list(mongo.db.orders.aggregate(monthly_earnings_pipeline))
        monthly_earnings = monthly_result[0]['total'] if monthly_result else 0
        
        return json_response({
            'success': True,
            'count': len(completed_orders),
            'data': completed_orders,
            'earnings': {
                'daily': daily_earnings,
                'monthly': monthly_earnings
            }
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/orders/<order_id>', methods=['GET'])
@protect
def get_order(order_id):
    """Get single order"""
    try:
        pipeline = [
            {'$match': {'_id': ObjectId(order_id)}},
            {'$lookup': {
                'from': 'canteens',
                'localField': 'canteenId',
                'foreignField': '_id',
                'as': 'canteenInfo'
            }},
            {'$lookup': {
                'from': 'users',
                'localField': 'userId',
                'foreignField': '_id',
                'as': 'userInfo'
            }},
            {'$addFields': {
                'canteenId': {
                    '$cond': {
                        'if': {'$gt': [{'$size': '$canteenInfo'}, 0]},
                        'then': {
                            '_id': {'$arrayElemAt': ['$canteenInfo._id', 0]},
                            'name': {'$arrayElemAt': ['$canteenInfo.name', 0]},
                            'location': {'$arrayElemAt': ['$canteenInfo.location', 0]}
                        },
                        'else': '$canteenId'
                    }
                },
                'userId': {
                    '$cond': {
                        'if': {'$gt': [{'$size': '$userInfo'}, 0]},
                        'then': {
                            '_id': {'$arrayElemAt': ['$userInfo._id', 0]},
                            'name': {'$arrayElemAt': ['$userInfo.name', 0]},
                            'email': {'$arrayElemAt': ['$userInfo.email', 0]}
                        },
                        'else': '$userId'
                    }
                }
            }},
            {'$project': {'canteenInfo': 0, 'userInfo': 0}}
        ]
        
        orders = list(mongo.db.orders.aggregate(pipeline))
        
        if not orders:
            return json_response({
                'success': False,
                'message': 'Order not found'
            }, 404)
        
        order = orders[0]
        
        # Check authorization
        user_id = order['userId']['_id'] if isinstance(order['userId'], dict) else order['userId']
        canteen_id = order['canteenId']['_id'] if isinstance(order['canteenId'], dict) else order['canteenId']
        
        if g.user['role'] == 'STUDENT' and str(user_id) != str(g.user['_id']):
            return json_response({
                'success': False,
                'message': 'Not authorized to view this order'
            }, 403)
        
        if g.user['role'] == 'CANTEEN' and str(canteen_id) != str(g.user.get('canteenId')):
            return json_response({
                'success': False,
                'message': 'Not authorized to view this order'
            }, 403)
        
        return json_response({
            'success': True,
            'data': order
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/orders/<order_id>/accept', methods=['POST'])
@protect
@authorize('CANTEEN', 'ADMIN')
def accept_order(order_id):
    """Accept an order"""
    try:
        order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
        
        if not order:
            return json_response({
                'success': False,
                'message': 'Order not found'
            }, 404)
        
        # Check if user is canteen owner
        if g.user['role'] == 'CANTEEN' and str(g.user.get('canteenId')) != str(order['canteenId']):
            return json_response({
                'success': False,
                'message': 'Not authorized to update this order'
            }, 403)
        
        if order['status'] != 'PAID':
            return json_response({
                'success': False,
                'message': 'Only paid orders can be accepted'
            }, 400)
        
        mongo.db.orders.update_one(
            {'_id': ObjectId(order_id)},
            {'$set': {'status': 'ACCEPTED', 'updatedAt': datetime.utcnow()}}
        )
        
        updated_order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
        
        return json_response({
            'success': True,
            'data': updated_order
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/orders/<order_id>/prepare', methods=['POST'])
@protect
@authorize('CANTEEN', 'ADMIN')
def prepare_order(order_id):
    """Mark order as preparing"""
    try:
        order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
        
        if not order:
            return json_response({
                'success': False,
                'message': 'Order not found'
            }, 404)
        
        # Check if user is canteen owner
        if g.user['role'] == 'CANTEEN' and str(g.user.get('canteenId')) != str(order['canteenId']):
            return json_response({
                'success': False,
                'message': 'Not authorized to update this order'
            }, 403)
        
        if order['status'] != 'ACCEPTED':
            return json_response({
                'success': False,
                'message': 'Only accepted orders can be marked as preparing'
            }, 400)
        
        mongo.db.orders.update_one(
            {'_id': ObjectId(order_id)},
            {'$set': {'status': 'PREPARING', 'updatedAt': datetime.utcnow()}}
        )
        
        updated_order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
        
        return json_response({
            'success': True,
            'data': updated_order
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/orders/<order_id>/ready', methods=['POST'])
@protect
@authorize('CANTEEN', 'ADMIN')
def ready_order(order_id):
    """Mark order as ready for pickup"""
    try:
        order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
        
        if not order:
            return json_response({
                'success': False,
                'message': 'Order not found'
            }, 404)
        
        # Check if user is canteen owner
        if g.user['role'] == 'CANTEEN' and str(g.user.get('canteenId')) != str(order['canteenId']):
            return json_response({
                'success': False,
                'message': 'Not authorized to update this order'
            }, 403)
        
        if order['status'] != 'PREPARING':
            return json_response({
                'success': False,
                'message': 'Only preparing orders can be marked as ready'
            }, 400)
        
        # Generate pickup code if not already generated
        pickup_code = order.get('pickupCode') or generate_pickup_code()
        
        mongo.db.orders.update_one(
            {'_id': ObjectId(order_id)},
            {'$set': {'status': 'READY', 'pickupCode': pickup_code, 'updatedAt': datetime.utcnow()}}
        )
        
        updated_order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
        
        return json_response({
            'success': True,
            'data': updated_order
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/orders/<order_id>/complete', methods=['POST'])
@protect
@authorize('CANTEEN', 'ADMIN')
def complete_order(order_id):
    """Complete order with pickup code"""
    data = request.get_json()
    pickup_code = data.get('pickupCode')
    
    try:
        order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
        
        if not order:
            return json_response({
                'success': False,
                'message': 'Order not found'
            }, 404)
        
        # Check if user is canteen owner
        if g.user['role'] == 'CANTEEN' and str(g.user.get('canteenId')) != str(order['canteenId']):
            return json_response({
                'success': False,
                'message': 'Not authorized to update this order'
            }, 403)
        
        if order['status'] != 'READY':
            return json_response({
                'success': False,
                'message': 'Only ready orders can be completed'
            }, 400)
        
        if order.get('pickupCodeUsed'):
            return json_response({
                'success': False,
                'message': 'Pickup code already used'
            }, 400)
        
        if order.get('pickupCode') != pickup_code:
            return json_response({
                'success': False,
                'message': 'Invalid pickup code'
            }, 400)
        
        mongo.db.orders.update_one(
            {'_id': ObjectId(order_id)},
            {'$set': {'status': 'COMPLETED', 'pickupCodeUsed': True, 'updatedAt': datetime.utcnow()}}
        )
        
        updated_order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
        
        return json_response({
            'success': True,
            'data': updated_order
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/orders/<order_id>/cancel', methods=['POST'])
@protect
def cancel_order(order_id):
    """Cancel an order"""
    try:
        order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
        
        if not order:
            return json_response({
                'success': False,
                'message': 'Order not found'
            }, 404)
        
        # Students can only cancel their own orders
        if g.user['role'] == 'STUDENT' and str(order['userId']) != str(g.user['_id']):
            return json_response({
                'success': False,
                'message': 'Not authorized to cancel this order'
            }, 403)
        
        # Can't cancel orders that are already preparing or ready
        if order['status'] in ['PREPARING', 'READY', 'COMPLETED']:
            return json_response({
                'success': False,
                'message': 'Cannot cancel order at this stage'
            }, 400)
        
        mongo.db.orders.update_one(
            {'_id': ObjectId(order_id)},
            {'$set': {'status': 'CANCELLED', 'updatedAt': datetime.utcnow()}}
        )
        
        updated_order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
        
        return json_response({
            'success': True,
            'data': updated_order
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

# ==================== PAYMENT ROUTES ====================

@app.route('/api/payments/initiate', methods=['POST'])
@protect
def initiate_payment():
    """Initiate payment for an order"""
    data = request.get_json()
    order_id = data.get('orderId')
    
    try:
        # Verify order exists
        order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
        
        if not order:
            return json_response({
                'success': False,
                'message': 'Order not found'
            }, 404)
        
        # Verify user owns the order
        if str(order['userId']) != str(g.user['_id']):
            return json_response({
                'success': False,
                'message': 'Not authorized to pay for this order'
            }, 403)
        
        # Check if order is in correct state
        if order['status'] != 'CREATED':
            return json_response({
                'success': False,
                'message': 'Order is not in a payable state'
            }, 400)
        
        # Check if payment already exists
        existing_payment = mongo.db.payments.find_one({
            'orderId': ObjectId(order_id),
            'status': {'$in': ['PENDING', 'SUCCESS']}
        })
        
        if existing_payment:
            return json_response({
                'success': False,
                'message': 'Payment already initiated for this order'
            }, 400)
        
        # Create payment record
        payment_data = {
            'orderId': ObjectId(order_id),
            'userId': g.user['_id'],
            'provider': 'MOCK',
            'amount': order['totalAmount'],
            'status': 'PENDING',
            'transactionId': None,
            'paymentDetails': {},
            'createdAt': datetime.utcnow(),
            'updatedAt': datetime.utcnow()
        }
        
        result = mongo.db.payments.insert_one(payment_data)
        payment_data['_id'] = result.inserted_id
        
        # Mock payment URL
        mock_payment_url = f"paytm://pay?amount={order['totalAmount']}&orderId={order_id}&paymentId={result.inserted_id}"
        
        return json_response({
            'success': True,
            'data': {
                'payment': payment_data,
                'paymentUrl': mock_payment_url,
                'qrData': json.dumps({
                    'paymentId': str(result.inserted_id),
                    'orderId': str(order_id),
                    'amount': order['totalAmount']
                })
            }
        }, 201)
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/payments/<payment_id>/confirm', methods=['POST'])
@protect
def confirm_payment(payment_id):
    """Confirm payment (mock endpoint for testing)"""
    try:
        payment = mongo.db.payments.find_one({'_id': ObjectId(payment_id)})
        
        if not payment:
            return json_response({
                'success': False,
                'message': 'Payment not found'
            }, 404)
        
        # Verify user owns the payment
        if str(payment['userId']) != str(g.user['_id']):
            return json_response({
                'success': False,
                'message': 'Not authorized'
            }, 403)
        
        if payment['status'] != 'PENDING':
            return json_response({
                'success': False,
                'message': 'Payment is not in pending state'
            }, 400)
        
        # Mock payment confirmation
        transaction_id = f"TXN{int(datetime.utcnow().timestamp() * 1000)}"
        
        mongo.db.payments.update_one(
            {'_id': ObjectId(payment_id)},
            {'$set': {
                'status': 'SUCCESS',
                'transactionId': transaction_id,
                'paymentDetails': {
                    'mockConfirmation': True,
                    'confirmedAt': datetime.utcnow().isoformat()
                },
                'updatedAt': datetime.utcnow()
            }}
        )
        
        # Update order status and generate pickup code
        pickup_code = generate_pickup_code()
        mongo.db.orders.update_one(
            {'_id': payment['orderId']},
            {'$set': {
                'status': 'PAID',
                'pickupCode': pickup_code,
                'updatedAt': datetime.utcnow()
            }}
        )
        
        updated_payment = mongo.db.payments.find_one({'_id': ObjectId(payment_id)})
        updated_order = mongo.db.orders.find_one({'_id': payment['orderId']})
        
        return json_response({
            'success': True,
            'data': {
                'payment': updated_payment,
                'order': updated_order
            }
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/payments/webhook/paytm', methods=['POST'])
def paytm_webhook():
    """Paytm webhook handler"""
    try:
        data = request.get_json()
        order_id = data.get('orderId')
        status = data.get('status')
        transaction_id = data.get('transactionId')
        
        payment = mongo.db.payments.find_one({'orderId': ObjectId(order_id)})
        
        if not payment:
            return json_response({
                'success': False,
                'message': 'Payment not found'
            }, 404)
        
        # Update payment status
        new_status = 'SUCCESS' if status == 'TXN_SUCCESS' else 'FAILED'
        
        mongo.db.payments.update_one(
            {'_id': payment['_id']},
            {'$set': {
                'status': new_status,
                'transactionId': transaction_id,
                'paymentDetails': data,
                'updatedAt': datetime.utcnow()
            }}
        )
        
        # Update order status
        order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
        
        if order:
            if new_status == 'SUCCESS':
                pickup_code = generate_pickup_code()
                mongo.db.orders.update_one(
                    {'_id': ObjectId(order_id)},
                    {'$set': {
                        'status': 'PAID',
                        'pickupCode': pickup_code,
                        'updatedAt': datetime.utcnow()
                    }}
                )
            else:
                mongo.db.orders.update_one(
                    {'_id': ObjectId(order_id)},
                    {'$set': {
                        'status': 'FAILED',
                        'updatedAt': datetime.utcnow()
                    }}
                )
        
        return json_response({
            'success': True,
            'message': 'Webhook processed'
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

@app.route('/api/payments/order/<order_id>', methods=['GET'])
@protect
def get_payment_for_order(order_id):
    """Get payment for an order"""
    try:
        payment = mongo.db.payments.find_one({'orderId': ObjectId(order_id)})
        
        if not payment:
            return json_response({
                'success': False,
                'message': 'Payment not found'
            }, 404)
        
        # Verify user owns the payment
        if str(payment['userId']) != str(g.user['_id']) and g.user['role'] != 'ADMIN':
            return json_response({
                'success': False,
                'message': 'Not authorized'
            }, 403)
        
        return json_response({
            'success': True,
            'data': payment
        })
        
    except Exception as e:
        return json_response({
            'success': False,
            'message': str(e)
        }, 500)

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(e):
    return json_response({
        'success': False,
        'message': 'Resource not found'
    }, 404)

@app.errorhandler(500)
def server_error(e):
    return json_response({
        'success': False,
        'message': 'Internal server error'
    }, 500)

# ==================== RUN SERVER ====================

if __name__ == '__main__':
    PORT = int(os.getenv('PORT', 5000))
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    print(f"""
╔════════════════════════════════════════════════════════════╗
║     Khana Management System - Flask Backend                ║
║     Server running on http://localhost:{PORT}                 ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG)
