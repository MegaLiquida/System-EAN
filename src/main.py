import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Importar modelos
from models import db, Tenant, User, Category, Supplier, Product, Stock, StockMovement, ProductExpiry

# ============================================================================
# CONFIGURAÇÃO DO FLASK
# ============================================================================

app = Flask(__name__)

# Configuração do banco de dados
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/mercado_db')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'

# Inicializar banco de dados
db.init_app(app)

# ============================================================================
# DECORADORES
# ============================================================================

def login_required(f):
    """Decorador para verificar se o usuário está autenticado"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or 'tenant_id' not in session:
            flash('Por favor, faça login primeiro.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Obter usuário atual da sessão"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

def get_current_tenant():
    """Obter tenant atual da sessão"""
    if 'tenant_id' in session:
        return Tenant.query.get(session['tenant_id'])
    return None

# ============================================================================
# ROTAS DE AUTENTICAÇÃO
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password) and user.is_active:
            session['user_id'] = user.id
            session['tenant_id'] = user.tenant_id
            session['username'] = user.username
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            flash(f'Bem-vindo, {user.full_name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Email ou senha inválidos.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Fazer logout"""
    session.clear()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Página de registro de novo mercado"""
    if request.method == 'POST':
        # Dados do tenant
        tenant_name = request.form.get('tenant_name')
        tenant_email = request.form.get('tenant_email')
        
        # Dados do usuário admin
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        
        # Verificar se tenant já existe
        if Tenant.query.filter_by(email=tenant_email).first():
            flash('Este email de mercado já está registrado.', 'danger')
            return redirect(url_for('register'))
        
        # Verificar se usuário já existe
        if User.query.filter_by(email=email).first():
            flash('Este email de usuário já está registrado.', 'danger')
            return redirect(url_for('register'))
        
        # Criar novo tenant
        tenant = Tenant(name=tenant_name, email=tenant_email)
        db.session.add(tenant)
        db.session.flush()
        
        # Criar usuário admin
        user = User(
            tenant_id=tenant.id,
            username=username,
            email=email,
            full_name=full_name,
            role='admin'
        )
        user.set_password(password)
        db.session.add(user)
        
        db.session.commit()
        
        flash('Mercado registrado com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# ============================================================================
# ROTAS PRINCIPAIS
# ============================================================================

@app.route('/')
@login_required
def dashboard():
    """Dashboard principal"""
    tenant = get_current_tenant()
    user = get_current_user()
    
    # Estatísticas
    total_products = Product.query.filter_by(tenant_id=tenant.id).count()
    
    # Alertas de estoque mínimo
    low_stock = db.session.query(Product, Stock).join(Stock).filter(
        Product.tenant_id == tenant.id,
        Stock.quantity < Product.minimum_stock
    ).all()
    
    # Alertas de validade
    today = datetime.utcnow().date()
    alert_date = today + timedelta(days=tenant.min_stock_alert_days)
    
    expiry_alerts = ProductExpiry.query.filter(
        ProductExpiry.tenant_id == tenant.id,
        ProductExpiry.expiry_date <= alert_date,
        ProductExpiry.status != 'expired'
    ).all()
    
    return render_template('dashboard.html', 
                         tenant=tenant, 
                         user=user,
                         total_products=total_products,
                         low_stock=low_stock,
                         expiry_alerts=expiry_alerts)

@app.route('/produtos')
@login_required
def products():
    """Página de produtos"""
    tenant = get_current_tenant()
    products = Product.query.filter_by(tenant_id=tenant.id).all()
    return render_template('products.html', products=products)

@app.route('/estoque')
@login_required
def stock():
    """Página de gestão de estoque"""
    tenant = get_current_tenant()
    products = Product.query.filter_by(tenant_id=tenant.id).all()
    return render_template('stock.html', products=products)

@app.route('/relatorios')
@login_required
def reports():
    """Página de relatórios"""
    tenant = get_current_tenant()
    return render_template('reports.html', tenant=tenant)

# ============================================================================
# ROTAS DE API (JSON)
# ============================================================================

@app.route('/api/produtos', methods=['GET'])
@login_required
def api_get_products():
    """API para obter produtos"""
    tenant = get_current_tenant()
    products = Product.query.filter_by(tenant_id=tenant.id).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'gtin': p.gtin,
        'brand': p.brand,
        'cost_price': p.cost_price,
        'sale_price': p.sale_price,
        'minimum_stock': p.minimum_stock
    } for p in products])

@app.route('/api/produtos', methods=['POST'])
@login_required
def api_create_product():
    """API para criar produto"""
    tenant = get_current_tenant()
    data = request.json
    
    try:
        product = Product(
            tenant_id=tenant.id,
            category_id=data.get('category_id'),
            supplier_id=data.get('supplier_id'),
            name=data.get('name'),
            description=data.get('description'),
            gtin=data.get('gtin'),
            brand=data.get('brand'),
            cost_price=float(data.get('cost_price')),
            sale_price=float(data.get('sale_price')),
            unit_of_measure=data.get('unit_of_measure', 'UN'),
            minimum_stock=int(data.get('minimum_stock', 0))
        )
        
        db.session.add(product)
        db.session.commit()
        
        return jsonify({'success': True, 'product_id': product.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/estoque/entrada', methods=['POST'])
@login_required
def api_stock_entry():
    """API para registrar entrada de estoque"""
    tenant = get_current_tenant()
    user = get_current_user()
    data = request.json
    
    try:
        product_id = data.get('product_id')
        quantity = int(data.get('quantity'))
        supplier_id = data.get('supplier_id')
        cost_price = float(data.get('cost_price'))
        expiry_date = data.get('expiry_date')
        
        # Atualizar estoque no armazém
        stock = Stock.query.filter_by(
            tenant_id=tenant.id,
            product_id=product_id,
            location='warehouse'
        ).first()
        
        if not stock:
            stock = Stock(
                tenant_id=tenant.id,
                product_id=product_id,
                location='warehouse',
                quantity=0
            )
            db.session.add(stock)
        
        stock.quantity += quantity
        
        # Registrar movimento
        movement = StockMovement(
            tenant_id=tenant.id,
            product_id=product_id,
            user_id=user.id,
            movement_type='entry',
            to_location='warehouse',
            quantity=quantity,
            supplier_id=supplier_id,
            cost_price=cost_price,
            notes=data.get('notes')
        )
        db.session.add(movement)
        
        # Registrar validade se fornecida
        if expiry_date:
            expiry = ProductExpiry(
                tenant_id=tenant.id,
                product_id=product_id,
                expiry_date=datetime.strptime(expiry_date, '%Y-%m-%d').date(),
                quantity=quantity,
                status='valid'
            )
            db.session.add(expiry)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Entrada registrada com sucesso'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/estoque/saida', methods=['POST'])
@login_required
def api_stock_exit():
    """API para registrar saída de estoque"""
    tenant = get_current_tenant()
    user = get_current_user()
    data = request.json
    
    try:
        product_id = data.get('product_id')
        quantity = int(data.get('quantity'))
        
        # Atualizar estoque na prateleira
        stock = Stock.query.filter_by(
            tenant_id=tenant.id,
            product_id=product_id,
            location='shelf'
        ).first()
        
        if not stock or stock.quantity < quantity:
            return jsonify({'success': False, 'error': 'Estoque insuficiente'}), 400
        
        stock.quantity -= quantity
        
        # Registrar movimento
        movement = StockMovement(
            tenant_id=tenant.id,
            product_id=product_id,
            user_id=user.id,
            movement_type='exit',
            from_location='shelf',
            quantity=quantity,
            notes=data.get('notes')
        )
        db.session.add(movement)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Saída registrada com sucesso'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

# ============================================================================
# TRATAMENTO DE ERROS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# ============================================================================
# CONTEXTO DE TEMPLATE
# ============================================================================

@app.context_processor
def inject_user():
    """Injetar usuário atual nos templates"""
    return {
        'current_user': get_current_user(),
        'current_tenant': get_current_tenant()
    }

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    port = int(os.getenv('PORT', 5000))
    app.run(debug=os.getenv('FLASK_ENV') == 'development', host='0.0.0.0', port=port)
