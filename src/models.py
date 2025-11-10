from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from enum import Enum

db = SQLAlchemy()

# ============================================================================
# MODELOS DE DADOS - SISTEMA DE GESTÃO DE MERCADO
# ============================================================================

class Tenant(db.Model):
    """Modelo para representar um cliente (mercado)"""
    __tablename__ = 'tenants'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(500))
    city = db.Column(db.String(100))
    state = db.Column(db.String(2))
    zip_code = db.Column(db.String(10))
    
    # Configurações
    min_stock_alert_days = db.Column(db.Integer, default=30)  # Dias para alerta de validade
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    users = db.relationship('User', backref='tenant', lazy=True, cascade='all, delete-orphan')
    categories = db.relationship('Category', backref='tenant', lazy=True, cascade='all, delete-orphan')
    suppliers = db.relationship('Supplier', backref='tenant', lazy=True, cascade='all, delete-orphan')
    products = db.relationship('Product', backref='tenant', lazy=True, cascade='all, delete-orphan')
    stock = db.relationship('Stock', backref='tenant', lazy=True, cascade='all, delete-orphan')
    movements = db.relationship('StockMovement', backref='tenant', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Tenant {self.name}>'


class User(db.Model):
    """Modelo para representar um usuário"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255))
    
    # Tipos de usuário: admin, estoquista, gerente
    role = db.Column(db.String(50), default='estoquista')
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Category(db.Model):
    """Modelo para categorias de produtos"""
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    products = db.relationship('Product', backref='category', lazy=True)
    
    __table_args__ = (db.UniqueConstraint('tenant_id', 'name', name='uq_tenant_category'),)
    
    def __repr__(self):
        return f'<Category {self.name}>'


class Supplier(db.Model):
    """Modelo para fornecedores"""
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(500))
    city = db.Column(db.String(100))
    state = db.Column(db.String(2))
    cnpj = db.Column(db.String(20))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    products = db.relationship('Product', backref='supplier', lazy=True)
    
    __table_args__ = (db.UniqueConstraint('tenant_id', 'name', name='uq_tenant_supplier'),)
    
    def __repr__(self):
        return f'<Supplier {self.name}>'


class Product(db.Model):
    """Modelo para produtos"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    gtin = db.Column(db.String(20))  # Código de barras
    brand = db.Column(db.String(255))
    
    # Preços
    cost_price = db.Column(db.Float, nullable=False)
    sale_price = db.Column(db.Float, nullable=False)
    
    # Estoque
    unit_of_measure = db.Column(db.String(10), default='UN')  # UN, KG, LT, M
    minimum_stock = db.Column(db.Integer, default=0)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    stock = db.relationship('Stock', backref='product', lazy=True, cascade='all, delete-orphan')
    movements = db.relationship('StockMovement', backref='product', lazy=True, cascade='all, delete-orphan')
    expiry = db.relationship('ProductExpiry', backref='product', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (db.UniqueConstraint('tenant_id', 'gtin', name='uq_tenant_gtin'),)
    
    def __repr__(self):
        return f'<Product {self.name}>'


class Stock(db.Model):
    """Modelo para controle de estoque por localização"""
    __tablename__ = 'stock'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    # Localização: 'warehouse' (armazém) ou 'shelf' (prateleira loja)
    location = db.Column(db.String(50), nullable=False)
    
    quantity = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'product_id', 'location', name='uq_tenant_product_location'),
    )
    
    def __repr__(self):
        return f'<Stock {self.product_id} - {self.location}: {self.quantity}>'


class StockMovement(db.Model):
    """Modelo para registrar movimentações de estoque"""
    __tablename__ = 'stock_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Tipos: 'entry' (entrada), 'exit' (saída), 'transfer' (transferência)
    movement_type = db.Column(db.String(50), nullable=False)
    
    # Localização de origem e destino
    from_location = db.Column(db.String(50))  # Para transferências
    to_location = db.Column(db.String(50))    # Para transferências
    
    quantity = db.Column(db.Integer, nullable=False)
    
    # Informações adicionais
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    cost_price = db.Column(db.Float)  # Para entradas
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    user = db.relationship('User', backref='movements')
    supplier = db.relationship('Supplier', backref='movements')
    
    def __repr__(self):
        return f'<StockMovement {self.movement_type}: {self.quantity}>'


class ProductExpiry(db.Model):
    """Modelo para controle de validade de produtos"""
    __tablename__ = 'product_expiry'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    # Data de validade
    expiry_date = db.Column(db.Date, nullable=False)
    
    # Quantidade com esta data de validade
    quantity = db.Column(db.Integer, default=0)
    
    # Status: 'valid' (válido), 'warning' (alerta), 'expired' (vencido)
    status = db.Column(db.String(50), default='valid')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProductExpiry {self.product_id} - {self.expiry_date}>'
