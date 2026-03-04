#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WEB APP - Análisis de Opciones con Autenticación
Aplicación web profesional con templates separados
"""

import sys
import os
import io
import locale
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception as e:
    print(f"[WARN] python-dotenv no disponible o falló: {e}")

# =============================================================================
# SOLUCIÓN 3: CONFIGURACIÓN DE LOCALE Y UTF-8 PARA COLAB Y OTROS ENTORNOS
# =============================================================================
# Esto es esencial para Google Colab y Windows que pueden usar ASCII por defecto
def configure_utf8_encoding():
    """
    Configura el sistema para usar UTF-8 de manera global.
    Especialmente importante para Google Colab y Windows.
    """
    # Configurar variables de entorno para UTF-8
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['LC_ALL'] = 'en_US.UTF-8'
    os.environ['LANG'] = 'en_US.UTF-8'
    
    # Intentar configurar locale (especialmente importante en Colab)
    try:
        # Intentar configurar locale UTF-8
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except locale.Error:
        try:
            # Fallback: intentar con C.UTF-8 (común en Linux/Colab)
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
        except locale.Error:
            try:
                # Fallback adicional: UTF-8 sin especificar región
                locale.setlocale(locale.LC_ALL, 'UTF-8')
            except locale.Error:
                # Si todo falla, continuar sin configurar locale
                pass
    
    # Configurar stdout, stderr y stdin para UTF-8
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        except:
            pass
    
    if sys.stderr.encoding != 'utf-8':
        try:
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except:
            pass
    
    if sys.stdin.encoding != 'utf-8':
        try:
            sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')
        except:
            pass
    
    # Intentar configurar el encoding por defecto (solo Python 2, pero por si acaso)
    try:
        if hasattr(sys, 'setdefaultencoding'):
            sys.setdefaultencoding('utf-8')
    except:
        pass

# Ejecutar configuración de UTF-8 al inicio
configure_utf8_encoding()

# =============================================================================
# SOLUCIÓN 3: Parche de Emergencia para Colab
# =============================================================================
# Si el error sale en print() o en mensajes de éxito, este parche lo resuelve
try:
    locale.getpreferredencoding = lambda: "UTF-8"
except:
    pass

# Capturar errores de inicialización temprana
try:
    import traceback
    sys.excepthook = lambda exc_type, exc_value, exc_traceback: (
        print(f"\n{'='*70}"),
        print(f"ERROR CRÍTICO DURANTE INICIALIZACIÓN"),
        print(f"{'='*70}"),
        print(f"Tipo: {exc_type.__name__}"),
        print(f"Mensaje: {exc_value}"),
        print(f"\nTraceback completo:"),
        traceback.print_exception(exc_type, exc_value, exc_traceback),
        print(f"{'='*70}\n")
    )
except:
    pass
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import json
import traceback
from functools import wraps
from datetime import timedelta
import hashlib
import secrets
try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False
    print("[WARN] bcrypt no disponible. Instala con: pip install bcrypt")
from collections import defaultdict
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

# Agregar paths posibles al sys.path
if '__file__' in globals():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, base_dir)
else:
    # Fallback para IPython/Jupyter/Colab
    base_dir = os.getcwd()
    sys.path.insert(0, base_dir)

# También intentar el directorio de trabajo actual
sys.path.insert(0, os.getcwd())

# Para Colab: asegurar que el directorio actual esté en el path
import os
current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)


# Importar módulos de análisis
try:
    from opciones_comparador import (
        black_scholes_advanced, black_scholes_vol_impl,
        binomial_op_val, binomial_vol_impl,
        bs93_amer, bs93_vol_impl
    )
    
    from analisis_griegas import (
        calcular_griegas_completas,
        analizar_escenarios
    )
    MODULES_LOADED = True
except ImportError as e:
    print(f"[WARN] No se pudieron cargar módulos de análisis: {e}")
    MODULES_LOADED = False

try:
    from trading_statistical_analysis import (
        descargar_datos, preparar_dataframe, calcular_retornos,
        calcular_volatilidad_historica,
        calcular_expected_move,
        calcular_distribucion_lognormal,
        calcular_probabilidades_implicitas,
        plot_probabilidad_distribucion
    )
    HAS_STAT_ANALYSIS = True
except ImportError as e:
    print(f"[WARN] trading_statistical_analysis no disponible: {e}")
    HAS_STAT_ANALYSIS = False

# Import portfolio modules
try:
    from core.pricing import OptionPricer
    from core.portfolio import Portfolio, OptionPosition
    from core.strategies import StrategyBuilder
    HAS_PORTFOLIO = True
except ImportError as e:
    print(f"[WARN] Portfolio modules not available: {e}")
    HAS_PORTFOLIO = False

# Import database module
try:
    import importlib
    import sys
    
    # Si el módulo ya está cargado, forzar recarga
    if 'core.database' in sys.modules:
        importlib.reload(sys.modules['core.database'])
        # También eliminar la instancia db si existe
        if 'core.database' in sys.modules and hasattr(sys.modules['core.database'], 'db'):
            delattr(sys.modules['core.database'], 'db')
    
    # Importar después del reload
    import core.database
    # Forzar recarga una vez más para asegurar
    importlib.reload(core.database)
    
    # Importar db después del reload
    from core.database import db
    
    # Verificar que db tiene el método actualizado
    import inspect
    sig = inspect.signature(db.create_user)
    if 'kwargs' not in sig.parameters:
        print("[WARN] create_user no tiene **kwargs, forzando recarga completa...")
        # Eliminar completamente del cache
        if 'core.database' in sys.modules:
            del sys.modules['core.database']
        import core.database
        from core.database import db
    
    HAS_DATABASE = True
    print("[INFO] Database module loaded and reloaded successfully")
except ImportError as e:
    print(f"[WARN] Database module not available: {e}")
    HAS_DATABASE = False
    db = None
except Exception as e:
    print(f"[WARN] Error loading database module: {e}")
    import traceback
    traceback.print_exc()
    HAS_DATABASE = False
    db = None

# Import subscription module
try:
    from core.subscription import subscription_manager, SubscriptionPlan
    HAS_SUBSCRIPTION = True
except ImportError as e:
    print(f"[WARN] Subscription module not available: {e}")
    HAS_SUBSCRIPTION = False

# Import chatbot module
try:
    from core.chatbot import chatbot
    HAS_CHATBOT = True
    print(f"[INFO] ✓ Chatbot module loaded successfully")
except ImportError as e:
    print(f"[WARN] Chatbot module not available: {e}")
    HAS_CHATBOT = False
    chatbot = None
except Exception as e:
    print(f"[ERROR] Error loading chatbot module: {e}")
    import traceback
    traceback.print_exc()
    HAS_CHATBOT = False
    chatbot = None

# Import logger and security modules
try:
    from core.logger import app_logger
    from core.security import security_manager
    HAS_LOGGER = True
    HAS_SECURITY = True
except ImportError as e:
    print(f"[WARN] Logger/Security modules not available: {e}")
    HAS_LOGGER = False
    HAS_SECURITY = False
    # Fallbacks
    class DummyLogger:
        def info(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): print(f"[ERROR] {args}")
        def warning(self, *args, **kwargs): pass
    app_logger = DummyLogger()
    security_manager = None

# Import backup module
try:
    from core.backup import backup_manager
    HAS_BACKUP = True
except ImportError as e:
    print(f"[WARN] Backup module not available: {e}")
    HAS_BACKUP = False
    backup_manager = None

# Configurar ruta de templates explícitamente
# En Colab, __file__ puede no estar definido - Detección robusta de templates
template_dir = None
possible_paths = []

# Intentar diferentes rutas para encontrar templates
try:
    if '__file__' in globals():
        possible_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))
    possible_paths.append(os.path.join(os.getcwd(), 'templates'))
    possible_paths.append('templates')
    possible_paths.append('/content/templates')  # Para Colab
    possible_paths.append('./templates')
    
    # Buscar la primera ruta que exista
    for path in possible_paths:
        if os.path.exists(path) and os.path.isdir(path):
            template_dir = path
            print(f"✓ Directorio de templates encontrado: {os.path.abspath(template_dir)}")
            break
    
    # Si no se encontró, usar 'templates' como relativo
    if template_dir is None:
        template_dir = 'templates'
        print(f"⚠️  No se encontró directorio de templates, usando: {template_dir}")
except Exception as e:
    print(f"[WARN] Error detectando template_dir: {e}")
    template_dir = 'templates'

# Crear app con template folder
try:
    # Intentar con ruta absoluta si existe
    if os.path.exists(template_dir) and os.path.isdir(template_dir):
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
        app = Flask(__name__, template_folder=template_dir, static_folder=static_dir, static_url_path='/static')
        print(f"✓ Flask creado con template_folder: {os.path.abspath(template_dir)}")
        print(f"✓ Flask creado con static_folder: {os.path.abspath(static_dir)}")
    else:
        # Usar relativo
        static_dir = 'static'
        app = Flask(__name__, template_folder='templates', static_folder=static_dir, static_url_path='/static')
        template_dir = 'templates'
        print(f"✓ Flask creado con template_folder relativo: templates")
        print(f"✓ Flask creado con static_folder relativo: static")
except Exception as e:
    print(f"[WARN] Error creando Flask con template_folder: {e}")
    # Fallback: sin especificar template_folder
    try:
        app = Flask(__name__)
        template_dir = 'templates'
        print(f"✓ Flask creado sin template_folder (usando default)")
    except Exception as e2:
        print(f"[ERROR] Error crítico creando Flask: {e2}")
        raise

# =============================================================================
# CONFIGURACIÓN DE ENTORNO (PRODUCCIÓN vs DESARROLLO)
# =============================================================================
FLASK_ENV = os.environ.get('FLASK_ENV', 'development').lower()
IS_PRODUCTION = FLASK_ENV == 'production'
IS_DEVELOPMENT = not IS_PRODUCTION

# Generate secure secret key - usar variable de entorno en producción
try:
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        if IS_PRODUCTION:
            raise ValueError("SECRET_KEY debe estar configurado en producción")
        secret_key = secrets.token_urlsafe(32)
        print("⚠️  ADVERTENCIA: Usando SECRET_KEY generado automáticamente. Configura SECRET_KEY en producción.")
    app.secret_key = secret_key
    app.permanent_session_lifetime = timedelta(hours=8)
except Exception as e:
    print(f"[WARN] Error configurando secret key: {e}")
    app.secret_key = 'dev-secret-key-change-in-production'
    app.permanent_session_lifetime = timedelta(hours=8)

# Configuración según entorno
app.config['DEBUG'] = IS_DEVELOPMENT
app.config['TESTING'] = False
app.config['ENV'] = FLASK_ENV
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# =============================================================================
# FLASK-SESSION: Sesiones persistentes del lado del servidor
# =============================================================================
# Esto evita que las sesiones se pierdan al reiniciar el servidor
try:
    from flask_session import Session
    
    # Directorio para almacenar sesiones
    session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd(), 'flask_session')
    os.makedirs(session_dir, exist_ok=True)
    
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = session_dir
    app.config['SESSION_PERMANENT'] = True
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_FILE_THRESHOLD'] = 500  # Máximo de sesiones en disco
    
    Session(app)
    print(f"✓ Flask-Session configurado (persistencia en: {session_dir})")
except ImportError:
    print("⚠️  flask-session no instalado. Sesiones solo en cookies (se pierden al reiniciar).")
    print("   Instala con: pip install flask-session")
except Exception as e:
    print(f"⚠️  Error configurando Flask-Session: {e}")

# =============================================================================
# BACKUP AUTOMÁTICO AL INICIAR
# =============================================================================
def run_startup_backup():
    """Ejecutar backup al iniciar la app (solo en producción)"""
    if not IS_PRODUCTION:
        return
    
    try:
        from core.backup import backup_manager
        
        # Crear backup de seguridad al iniciar
        backup_path = backup_manager.backup_database(compress=True)
        if backup_path:
            print(f"✓ Backup de inicio creado: {backup_path}")
        
        # Limpiar sesiones expiradas de la BD
        if HAS_DATABASE and db:
            db.cleanup_expired_sessions()
            print("✓ Sesiones expiradas limpiadas")
        
        # Limpiar backups antiguos
        cleaned = backup_manager.cleanup_old_backups(days_to_keep=7)
        if cleaned > 0:
            print(f"✓ {cleaned} backups antiguos eliminados")
    except Exception as e:
        print(f"⚠️  Error en backup de inicio: {e}")

# Ejecutar backup al iniciar (después de que todo esté cargado)
# Se ejecutará más adelante cuando HAS_DATABASE esté definido

# Configuración de CORS permitidos (solo en producción)
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '').split(',')
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]

if IS_PRODUCTION:
    print("🔒 MODO PRODUCCIÓN activado")
    if not ALLOWED_ORIGINS:
        print("⚠️  ADVERTENCIA: ALLOWED_ORIGINS no configurado. Configura dominios permitidos.")
    else:
        print(f"✓ CORS configurado para: {', '.join(ALLOWED_ORIGINS)}")
else:
    print("🔧 MODO DESARROLLO activado")

# Verificar templates disponibles
try:
    # Verificar el template_dir configurado
    if os.path.exists(template_dir) and os.path.isdir(template_dir):
        templates_available = os.listdir(template_dir)
        print(f"✓ Templates configurados en: {os.path.abspath(template_dir)}")
        print(f"   Templates encontrados: {len(templates_available)} archivos")
        if 'signup.html' not in templates_available:
            print(f"   ⚠️  ADVERTENCIA: signup.html no encontrado en {template_dir}")
        print(f"   Templates disponibles: {', '.join(templates_available[:10])}")
        # Asegurar que Flask use este directorio
        app.template_folder = template_dir
    else:
        print(f"⚠️  ADVERTENCIA: Directorio de templates no existe: {template_dir}")
        print(f"   Directorio actual: {os.getcwd()}")
        print(f"   Intentando buscar templates en otras ubicaciones...")
        
        # Buscar templates en otras ubicaciones
        search_paths = [
            os.path.join(os.getcwd(), 'templates'),
            '/content/templates',
            './templates',
            'templates'
        ]
        found = False
        for path in search_paths:
            if os.path.exists(path) and os.path.isdir(path):
                print(f"   ✓ Templates encontrados en: {os.path.abspath(path)}")
                templates_available = os.listdir(path)
                print(f"   Templates: {', '.join(templates_available[:10])}")
                # Actualizar template_dir y Flask
                template_dir = path
                app.template_folder = path
                found = True
                break
        
        if not found:
            print(f"   ✗ No se encontraron templates en ninguna ubicación")
            print(f"   Asegúrate de que la carpeta 'templates' existe en el directorio de trabajo")
            print(f"   Directorio actual: {os.getcwd()}")
            print(f"   Contenido del directorio: {os.listdir('.')[:10] if os.path.exists('.') else 'N/A'}")
except Exception as e:
    print(f"⚠️  Error verificando templates: {e}")
    import traceback
    traceback.print_exc()
# Ya configurado arriba según el entorno

# =============================================================================
# CONFIGURACIÓN DE LOGGING
# =============================================================================
# Configurar logging estructurado con rotación de archivos
try:
    if '__file__' in globals():
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    else:
        # Fallback para entornos sin __file__ (Colab, etc.)
        log_dir = os.path.join(os.getcwd(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
except Exception as e:
    print(f"[WARN] Error creando directorio de logs: {e}")
    log_dir = None

# Configurar handlers de logging solo si el directorio existe
file_handler = None
error_handler = None
auth_handler = None
auth_logger = None

if log_dir:
    try:
        # Handler para archivo de log general
        # CAUSA 10: Configurar logging con UTF-8 explícito
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'app.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'  # Forzar UTF-8 en el handler
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s [%(pathname)s:%(lineno)d]'
        ))

        # Handler para archivo de errores
        error_handler = RotatingFileHandler(
            os.path.join(log_dir, 'errors.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'  # Forzar UTF-8 en el handler
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s\n%(pathname)s:%(lineno)d\n%(exc_info)s'
        ))

        # Handler para autenticación
        auth_handler = RotatingFileHandler(
            os.path.join(log_dir, 'auth.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'  # Forzar UTF-8 en el handler
        )
        auth_handler.setLevel(logging.INFO)
        auth_handler.setFormatter(logging.Formatter(
            '%(asctime)s [AUTH] %(message)s'
        ))

        # Configurar logger de Flask
        app.logger.setLevel(logging.INFO)
        if file_handler:
            app.logger.addHandler(file_handler)
        if error_handler:
            app.logger.addHandler(error_handler)

        # Logger específico para autenticación
        auth_logger = logging.getLogger('auth')
        auth_logger.setLevel(logging.INFO)
        if auth_handler:
            auth_logger.addHandler(auth_handler)
        auth_logger.propagate = False

        # Configurar nivel de logging según entorno
        if IS_PRODUCTION:
            app.logger.setLevel(logging.WARNING)  # Solo warnings y errores en producción
            file_handler.setLevel(logging.INFO)  # Pero guardar info en archivo
        else:
            app.logger.setLevel(logging.DEBUG)  # Todo en desarrollo
        
        print(f"✓ Sistema de logging configurado. Logs en: {log_dir}")
        if IS_PRODUCTION:
            print(f"   Modo: PRODUCCIÓN (nivel: WARNING en consola, INFO en archivo)")
        else:
            print(f"   Modo: DESARROLLO (nivel: DEBUG)")
    except Exception as e:
        print(f"[WARN] Error configurando logging: {e}")
        # Crear logger dummy para evitar errores
        auth_logger = logging.getLogger('auth')
        auth_logger.setLevel(logging.WARNING)
        auth_logger.addHandler(logging.NullHandler())
else:
    print("[WARN] Logging deshabilitado (no se pudo crear directorio de logs)")
    # Crear logger dummy
    auth_logger = logging.getLogger('auth')
    auth_logger.setLevel(logging.WARNING)
    auth_logger.addHandler(logging.NullHandler())

# =============================================================================
# CONFIGURACIÓN DE EMAIL (SMTP)
# =============================================================================
# Configuración de email desde variables de entorno
MAIL_CONFIG = {
    'MAIL_SERVER': os.environ.get('MAIL_SERVER', 'smtp.gmail.com'),
    'MAIL_PORT': int(os.environ.get('MAIL_PORT', 587)),
    'MAIL_USE_TLS': os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true',
    'MAIL_USERNAME': os.environ.get('MAIL_USERNAME', ''),
    'MAIL_PASSWORD': os.environ.get('MAIL_PASSWORD', ''),
    'MAIL_FROM': os.environ.get('MAIL_FROM', os.environ.get('MAIL_USERNAME', 'noreply@example.com'))
}

# Intentar importar Flask-Mail
HAS_MAIL = False
mail = None
try:
    from flask_mail import Mail, Message
    HAS_MAIL = True
    try:
        mail = Mail()
        # Configurar Flask-Mail
        app.config['MAIL_SERVER'] = MAIL_CONFIG['MAIL_SERVER']
        app.config['MAIL_PORT'] = MAIL_CONFIG['MAIL_PORT']
        app.config['MAIL_USE_TLS'] = MAIL_CONFIG['MAIL_USE_TLS']
        app.config['MAIL_USERNAME'] = MAIL_CONFIG['MAIL_USERNAME']
        app.config['MAIL_PASSWORD'] = MAIL_CONFIG['MAIL_PASSWORD']
        app.config['MAIL_DEFAULT_SENDER'] = MAIL_CONFIG['MAIL_FROM']
        app.config['MAIL_DEFAULT_CHARSET'] = 'utf-8'  # Asegurar UTF-8 para caracteres especiales
        mail.init_app(app)
        
        if MAIL_CONFIG['MAIL_USERNAME'] and MAIL_CONFIG['MAIL_PASSWORD']:
            print(f"✓ Email configurado: {MAIL_CONFIG['MAIL_USERNAME']}")
        else:
            print("⚠️  Email no configurado. Configura MAIL_USERNAME y MAIL_PASSWORD para habilitar envío de emails.")
            HAS_MAIL = False
    except Exception as e:
        HAS_MAIL = False
        print(f"[WARN] Error configurando Flask-Mail: {e}")
        mail = None
except ImportError:
    HAS_MAIL = False
    print("[WARN] Flask-Mail no disponible. Instala con: pip install flask-mail")
    mail = None

# =============================================================================
# FUNCIONES DE RECUPERACIÓN DE CLAVE
# =============================================================================

def generate_reset_token():
    """
    Genera un token seguro y único para reset de clave
    Retorna: token (string URL-safe), expires_at (datetime)
    """
    import secrets
    from datetime import datetime, timedelta
    
    # Generar token URL-safe de 32 bytes (44 caracteres en base64)
    token = secrets.token_urlsafe(32)
    
    # Tiempo de expiración: 1 hora desde ahora
    expires_at = datetime.now() + timedelta(hours=1)
    
    return token, expires_at

def send_reset_password_email(email_or_username, reset_token, verification_code=None):
    """
    Enviar email con link de reset de clave
    MÉTODO ULTRA SIMPLE: Retorna solo True/False, sin mensajes de error
    """
    import smtplib
    
    # Envolver TODO en try-except múltiple para capturar CUALQUIER error
    # Incluyendo errores de encoding que ocurran en cualquier lugar
    try:
        # Si no hay contraseña o email configurado, retornar False
        if not MAIL_CONFIG['MAIL_USERNAME'] or not MAIL_CONFIG['MAIL_PASSWORD']:
            return False, None
        
        # Determinar email del usuario
        recipient_email = None
        try:
            if '@' in str(email_or_username):
                recipient_email = str(email_or_username).encode('ascii', errors='replace').decode('ascii')
            else:
                if HAS_DATABASE and db:
                    user = db.get_user(email_or_username)
                    if user and user.get('email'):
                        recipient_email = str(user['email']).encode('ascii', errors='replace').decode('ascii')
                    else:
                        return False, None
                else:
                    return False, None
        except:
            return False, None
        
        if not recipient_email:
            return False, None
        
        # Obtener URL base
        try:
            base_url = str(request.host_url.rstrip('/')).encode('ascii', errors='replace').decode('ascii')
        except:
            base_url = str(os.environ.get('APP_BASE_URL', 'http://localhost:5000')).encode('ascii', errors='replace').decode('ascii')
        
        # Construir URL
        reset_token_safe = str(reset_token).encode('ascii', errors='replace').decode('ascii')
        reset_url = base_url + "/reset_password?token=" + reset_token_safe
        
        # Construir email 100% ASCII
        email_lines = [
            "Hello,",
            "",
            "We received a request to recover your password.",
            "",
            "Your verification code is:",
            verification_code if verification_code else "N/A",
            "",
            "Enter this code on the password reset page to verify your identity.",
            "",
            "To reset your password, click here:",
            reset_url,
            "",
            "Or copy and paste the link above in your browser.",
            "",
            "This code and link will expire in 1 hour.",
            "",
            "If you did not request this change, you can safely ignore this email.",
            "",
            "This is an automatic email, please do not reply.",
            "",
            "Best regards,",
            "Support Team"
        ]
        email_body = "\r\n".join(email_lines)
        
        subject_text = "Recover Password - Click here to reset"
        mail_from_safe = str(MAIL_CONFIG['MAIL_FROM']).encode('ascii', errors='replace').decode('ascii')
        
        message_parts = [
            "From: " + mail_from_safe,
            "To: " + recipient_email,
            "Subject: " + subject_text,
            "MIME-Version: 1.0",
            "Content-Type: text/plain; charset=utf-8",
            "Content-Transfer-Encoding: 8bit",
            "",
            email_body
        ]
        
        full_message = "\r\n".join(message_parts)
        full_message = full_message.encode('ascii', errors='replace').decode('ascii')
        message_bytes = full_message.encode('utf-8')
        
        # Enviar email
        server = None
        try:
            server = smtplib.SMTP(MAIL_CONFIG['MAIL_SERVER'], MAIL_CONFIG['MAIL_PORT'])
            if MAIL_CONFIG['MAIL_USE_TLS']:
                server.starttls()
            server.login(MAIL_CONFIG['MAIL_USERNAME'], MAIL_CONFIG['MAIL_PASSWORD'])
            server.sendmail(mail_from_safe, [recipient_email], message_bytes)
            # Si llegamos aquí, el email se envió exitosamente
            return True, None
        except Exception as e:
            # Si hay error al enviar, retornar False
            return False, None
        finally:
            if server:
                try:
                    server.quit()
                except:
                    try:
                        server.close()
                    except:
                        pass
        
    except UnicodeEncodeError:
        # Capturar errores de encoding en el try externo también
        return False, None
    except Exception:
        # Capturar cualquier otro error en el try externo
        return False, None

# Rate limiting
request_log = defaultdict(list)
MAX_REQUESTS_PER_MINUTE = 60

# =============================================================================
# PROTECCIÓN CSRF BÁSICA
# =============================================================================
# Para producción, se recomienda usar Flask-WTF, pero aquí implementamos una versión básica
CSRF_ENABLED = IS_PRODUCTION or os.environ.get('ENABLE_CSRF', 'false').lower() == 'true'

def generate_csrf_token():
    """Generar token CSRF para la sesión"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf_token(token):
    """Validar token CSRF"""
    if not CSRF_ENABLED:
        return True  # Deshabilitado en desarrollo por defecto
    return token and token == session.get('csrf_token')

# =============================================================================
# FUNCIÓN HELPER: Sanitizar strings para evitar problemas de encoding
# =============================================================================
def safe_string(text, for_json=False):
    """
    Sanitiza un string para evitar problemas de encoding.
    Si for_json=True, reemplaza caracteres especiales.
    Si for_json=False, intenta mantenerlos pero los codifica de forma segura.
    """
    if not text or not isinstance(text, str):
        return text
    
    try:
        # Verificar que se puede codificar en UTF-8
        text.encode('utf-8')
        if for_json:
            # Para JSON, mantener los caracteres pero asegurar que sean válidos
            return text
        else:
            # Para print/logger, mantener los caracteres
            return text
    except UnicodeEncodeError:
        # Si hay problema, reemplazar caracteres especiales
        return text.replace('ñ', 'n').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u').replace('Ñ', 'N').replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')

def safe_print(*args, **kwargs):
    """Wrapper seguro para print() que maneja UTF-8"""
    try:
        # Intentar imprimir normalmente
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Si falla, sanitizar los argumentos
        sanitized_args = [safe_string(str(arg), for_json=False) if isinstance(arg, str) else arg for arg in args]
        try:
            print(*sanitized_args, **kwargs)
        except:
            # Último recurso: imprimir sin caracteres especiales
            print(*[str(arg).encode('ascii', errors='replace').decode('ascii') if isinstance(arg, str) else arg for arg in args], **kwargs)

# =============================================================================
# CAUSA 11: Wrapper seguro para jsonify que asegura UTF-8
# =============================================================================
def safe_jsonify(*args, **kwargs):
    """
    Wrapper para jsonify que asegura que todos los datos estén en UTF-8
    y sanitiza cualquier caracter especial que pueda causar problemas
    """
    def sanitize_value(value):
        """Sanitiza recursivamente valores para JSON"""
        if isinstance(value, str):
            # Sanitizar PRIMERO antes de intentar codificar
            # Reemplazar TODOS los caracteres especiales para asegurar ASCII puro
            sanitized = value.replace('ñ', 'n').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            sanitized = sanitized.replace('Ñ', 'N').replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')
            # Verificar que se pueda codificar en ASCII (más estricto que UTF-8)
            try:
                sanitized.encode('ascii')
                return sanitized
            except UnicodeEncodeError:
                # Si todavía falla, usar encode con errors='replace'
                return sanitized.encode('ascii', errors='replace').decode('ascii')
        elif isinstance(value, dict):
            return {k: sanitize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [sanitize_value(item) for item in value]
        else:
            return value
    
    # Si se pasa un diccionario como primer argumento posicional
    if args and isinstance(args[0], dict):
        sanitized_data = sanitize_value(args[0])
        return jsonify(sanitized_data, **kwargs)
    # Si se pasan kwargs
    elif kwargs:
        sanitized_kwargs = sanitize_value(kwargs)
        return jsonify(**sanitized_kwargs)
    else:
        return jsonify(*args, **kwargs)

def require_csrf(f):
    """Decorador para requerir CSRF en endpoints POST"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST' and CSRF_ENABLED:
            # Obtener token del header o form
            token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
            if not token or not validate_csrf_token(token):
                return safe_jsonify({'success': False, 'error': 'Token CSRF invalido'}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.after_request
def after_request(response):
    """
    Configurar headers de seguridad y CORS según el entorno
    """
    # =============================================================================
    # SOLUCIÓN CRÍTICA: Asegurar Content-Type con charset UTF-8 para HTML
    # =============================================================================
    # Esto es esencial para que los caracteres especiales se muestren correctamente
    content_type = response.content_type or ''
    if 'text/html' in content_type or (not content_type and response.is_json == False):
        # Si es HTML o no tiene content-type definido (probablemente HTML)
        if 'charset' not in content_type.lower():
            response.content_type = 'text/html; charset=utf-8'
    elif response.is_json:
        # Para JSON, asegurar charset UTF-8
        if 'charset' not in content_type.lower():
            response.content_type = 'application/json; charset=utf-8'
    
    # CORS Configuration
    origin = request.headers.get('Origin', '')
    if IS_PRODUCTION:
        # En producción: solo permitir orígenes específicos
        if ALLOWED_ORIGINS:
            if origin in ALLOWED_ORIGINS:
                response.headers.add('Access-Control-Allow-Origin', origin)
            else:
                # Si no hay origen permitido, no agregar header (más seguro)
                pass
        else:
            # Si no hay ALLOWED_ORIGINS configurado, permitir el origen actual como fallback
            if origin:
                response.headers.add('Access-Control-Allow-Origin', origin)
    else:
        # En desarrollo: permitir todos los orígenes
        response.headers.add('Access-Control-Allow-Origin', '*')
    
    # Headers CORS comunes
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS,PATCH')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    response.headers.add('Access-Control-Max-Age', '3600')
    
    # Security Headers (solo en producción o si está habilitado)
    if IS_PRODUCTION or os.environ.get('ENABLE_SECURITY_HEADERS', 'false').lower() == 'true':
        # Prevenir clickjacking
        response.headers.add('X-Frame-Options', 'DENY')
        
        # Prevenir MIME type sniffing
        response.headers.add('X-Content-Type-Options', 'nosniff')
        
        # XSS Protection (legacy, pero útil)
        response.headers.add('X-XSS-Protection', '1; mode=block')
        
        # Referrer Policy
        response.headers.add('Referrer-Policy', 'strict-origin-when-cross-origin')
        
        # Content Security Policy básica
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers.add('Content-Security-Policy', csp)
        
        # HSTS (solo si está en HTTPS)
        if request.is_secure or os.environ.get('FORCE_HSTS', 'false').lower() == 'true':
            response.headers.add('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    
    # Log de requests con errores
    try:
        if response.status_code >= 400:
            app.logger.warning(
                f"{request.method} {request.path} - Status: {response.status_code} desde {request.remote_addr}"
            )
    except:
        pass
    
    return response

@app.errorhandler(500)
def internal_error(error):
    """Manejo de errores 500"""
    import traceback
    error_trace = traceback.format_exc()
    
    # Log del error
    try:
        app.logger.error(
            f"Error 500 en {request.method} {request.path} desde {request.remote_addr}",
            exc_info=True
        )
    except:
        print(f"ERROR 500: {error}")
        print(f"Traceback: {error_trace}")
    
    # Imprimir en consola para debugging
    print(f"\n{'='*70}")
    print(f"ERROR 500 - {request.method} {request.path}")
    print(f"{'='*70}")
    print(f"Error: {error}")
    print(f"Traceback:\n{error_trace}")
    print(f"{'='*70}\n")
    
    return jsonify({
        'error': 'Internal Server Error',
        'message': str(error),
        'path': request.path,
        'method': request.method,
        'traceback': error_trace if app.debug else None
    }), 500

@app.errorhandler(404)
def not_found(error):
    """Manejo de errores 404"""
    # Log del 404
    try:
        app.logger.warning(f"404 - Ruta no encontrada: {request.method} {request.path} desde {request.remote_addr}")
    except:
        pass
    
    # Si es una petición API, devolver JSON con más información
    if request.path.startswith('/api/'):
        # Listar rutas disponibles para debugging
        available_routes = [str(rule) for rule in app.url_map.iter_rules() if '/api/' in str(rule)]
        return jsonify({
            'error': 'Not Found',
            'message': f'Ruta no encontrada: {request.path}',
            'method': request.method,
            'available_api_routes': sorted(available_routes)[:20]  # Primeras 20 para no saturar
        }), 404
    return jsonify({'error': 'Not Found', 'message': str(error)}), 404

# =============================================================================
# AUTENTICACIÓN CON HASHING DE CLAVES
# =============================================================================
# Autenticación con hashing de claves
def hash_password(password):
    """
    Hash password usando bcrypt (recomendado) o SHA-256 (fallback)
    bcrypt es más seguro: incluye salt automático y es resistente a timing attacks
    """
    if HAS_BCRYPT:
        # bcrypt: más seguro, incluye salt automático
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    else:
        # Fallback a SHA-256 (menos seguro, solo para desarrollo)
        print("[WARN] Usando SHA-256 como fallback. Instala bcrypt para producción.")
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    """
    Verificar clave contra hash almacenado
    Compatible con bcrypt y SHA-256 (legacy)
    """
    if HAS_BCRYPT:
        try:
            # Intentar verificar con bcrypt
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except (ValueError, TypeError):
            # Si falla, puede ser hash SHA-256 legacy
            return hashlib.sha256(password.encode()).hexdigest() == hashed
    else:
        # Fallback a SHA-256
        return hashlib.sha256(password.encode()).hexdigest() == hashed

# =============================================================================
# CONFIGURACIÓN DE USUARIOS
# =============================================================================
# Puedes configurar usuarios de dos formas:
#
# 1. VARIABLES DE ENTORNO (recomendado para producción):
#    Ejemplo: export APP_USER_admin=mi_clave_segura
#             export APP_USER_trader=otra_clave
#
# 2. ARCHIVO .env (alternativa):
#    Crear archivo .env en el mismo directorio:
#    APP_USER_admin=mi_clave_segura
#    APP_USER_trader=otra_clave
#    APP_USER_analyst=tercera_clave
#
# 3. MODIFICAR DIRECTAMENTE ESTE DICCIONARIO (más simple):
#    Cambia los valores después de hash_password() con tus propias claves
# =============================================================================

# Sistema de usuarios: usar base de datos si está disponible, sino diccionario en memoria
USERS = {}  # Fallback para compatibilidad

# Intentar cargar usuarios desde base de datos
try:
    if HAS_DATABASE and db:
        try:
            # Migrar usuarios de variables de entorno a base de datos si existen
            for key, value in os.environ.items():
                if key.startswith('APP_USER_'):
                    username = key.replace('APP_USER_', '').lower()
                    password = value
                    try:
                        # Verificar si el usuario ya existe en BD
                        existing_user = db.get_user(username)
                        if not existing_user:
                            # Crear usuario en BD
                            password_hash = hash_password(password)
                            if db.create_user(username, password_hash, role='admin'):
                                print(f"✓ Usuario '{username}' creado en base de datos desde variable de entorno")
                            else:
                                print(f"⚠️  No se pudo crear usuario '{username}' en BD")
                        else:
                            print(f"✓ Usuario '{username}' ya existe en base de datos")
                    except Exception as e:
                        print(f"[WARN] Error procesando usuario {username}: {e}")
                        # Agregar a diccionario como fallback
                        USERS[username] = hash_password(password)
            
            # Si no hay usuarios en BD ni en variables de entorno, crear usuarios por defecto
            try:
                users_in_db = db.list_users(active_only=False)
                if not users_in_db:
                    print("⚠️  No hay usuarios en base de datos.")
                    print("   Creando usuarios por defecto (CAMBIAR EN PRODUCCIÓN):")
                    
                    default_users = {
                        'admin': ('admin123', 'admin'),
                        'trader': ('trader123', 'user'),
                        'analyst': ('analyst123', 'user')
                    }
                    
                    for username, (password, role) in default_users.items():
                        try:
                            password_hash = hash_password(password)
                            if db.create_user(username, password_hash, role=role):
                                print(f"   ✓ {username} / {password} (rol: {role})")
                            else:
                                print(f"   ✗ Error creando {username}")
                        except Exception as e:
                            print(f"   ✗ Error creando {username}: {e}")
                    
                    print("\n   ⚠️  IMPORTANTE: Cambia estas claves en produccion!")
                else:
                    print(f"\n✓ {len(users_in_db)} usuario(s) en base de datos")
            except Exception as e:
                print(f"[WARN] Error listando usuarios de BD: {e}")
        except Exception as e:
            print(f"[WARN] Error inicializando usuarios en BD: {e}")
            print("   Usando sistema de usuarios en memoria como fallback")
            # Fallback a sistema anterior
            for key, value in os.environ.items():
                if key.startswith('APP_USER_'):
                    username = key.replace('APP_USER_', '').lower()
                    try:
                        USERS[username] = hash_password(value)
                    except:
                        pass
    else:
        # Fallback: sistema anterior sin base de datos
        print("[WARN] Base de datos no disponible. Usando sistema de usuarios en memoria.")
        for key, value in os.environ.items():
            if key.startswith('APP_USER_'):
                username = key.replace('APP_USER_', '').lower()
                password = value
                try:
                    USERS[username] = hash_password(password)
                    print(f"✓ Usuario '{username}' cargado desde variable de entorno")
                except:
                    pass

        if not USERS:
            print("⚠️  No se encontraron usuarios en variables de entorno.")
            print("   Usando usuarios por defecto (CAMBIAR EN PRODUCCIÓN):")
            try:
                USERS = {
                    'admin': hash_password('admin123'),
                    'trader': hash_password('trader123'),
                    'analyst': hash_password('analyst123')
                }
                print("   admin / admin123")
                print("   trader / trader123")
                print("   analyst / analyst123")
            except Exception as e:
                print(f"[ERROR] Error creando usuarios por defecto: {e}")
except Exception as e:
    print(f"[ERROR] Error crítico inicializando sistema de usuarios: {e}")
    import traceback
    traceback.print_exc()
    # Asegurar que al menos hay un diccionario vacío
    if not USERS:
        USERS = {}

def rate_limit(f):
    """Rate limiting decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        now = datetime.now()
        
        # Limpiar requests antiguos
        request_log[client_ip] = [
            req_time for req_time in request_log[client_ip]
            if (now - req_time).seconds < 60
        ]
        
        # Verificar límite
        if len(request_log[client_ip]) >= MAX_REQUESTS_PER_MINUTE:
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        request_log[client_ip].append(now)
        return f(*args, **kwargs)
    return decorated_function

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            # Si es una petición JSON/API, devolver JSON
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'No autenticado'}), 401
            # Si es HTML, hacer redirect
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/health', methods=['GET'])
def api_health():
    """Endpoint de diagnóstico mejorado con métricas"""
    # Intentar importar psutil para métricas del sistema
    HAS_PSUTIL = False
    try:
        import psutil
        HAS_PSUTIL = True
    except ImportError:
        pass
        
    health_status = {
        'status': 'ok',
        'server': 'running',
        'environment': FLASK_ENV,
        'is_production': IS_PRODUCTION,
        'timestamp': datetime.now().isoformat(),
        'modules': {
            'portfolio': HAS_PORTFOLIO,
            'analysis_modules': MODULES_LOADED,
            'database': HAS_DATABASE,
            'bcrypt': HAS_BCRYPT,
            'mail': HAS_MAIL and MAIL_CONFIG['MAIL_USERNAME'] and MAIL_CONFIG['MAIL_PASSWORD'],
            'backup': HAS_BACKUP,
            'security': HAS_SECURITY,
            'logger': HAS_LOGGER
        }
    }
    
    # Métricas del sistema si psutil está disponible
    if HAS_PSUTIL:
        try:
            health_status['system'] = {
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent
            }
        except:
            pass
    
    # Información de base de datos
    if HAS_DATABASE and db:
        try:
            users_count = len(db.list_users(active_only=True))
            health_status['database_info'] = {
                'users_count': users_count,
                'db_exists': os.path.exists('trading_app.db'),
                'db_size_mb': round(os.path.getsize('trading_app.db') / (1024 * 1024), 2) if os.path.exists('trading_app.db') else 0
            }
        except:
            pass
    
    # Información de backups
    if HAS_BACKUP and backup_manager:
        try:
            backup_info = backup_manager.get_backup_info()
            health_status['backups'] = {
                'daily_count': len(backup_info['daily']),
                'weekly_count': len(backup_info['weekly']),
                'monthly_count': len(backup_info['monthly']),
                'total_size_mb': backup_info['total_size_mb']
            }
        except:
            pass
    
    return jsonify(health_status), 200

@app.route('/api/debug/test', methods=['GET'])
def debug_test():
    """Endpoint de prueba para verificar que todo funciona"""
    try:
        return jsonify({
            'success': True,
            'message': 'Server is working',
            'app_initialized': app is not None,
            'has_database': HAS_DATABASE,
            'has_portfolio': HAS_PORTFOLIO
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/backup/create', methods=['POST'])
@require_auth
@rate_limit
def api_create_backup():
    """Crear backup manual de la base de datos"""
    if not HAS_BACKUP or not backup_manager:
        return jsonify({'success': False, 'error': 'Sistema de backup no disponible'}), 503
    
    try:
        backup_path = backup_manager.backup_database(compress=True)
        if backup_path:
            # También hacer backup de logs
            log_backups = backup_manager.backup_logs()
            
            return jsonify({
                'success': True,
                'message': 'Backup creado exitosamente',
                'backup_path': backup_path,
                'log_backups': log_backups,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'success': False, 'error': 'No se pudo crear el backup'}), 500
    except Exception as e:
        app.logger.error(f"Error creando backup: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/backup/info', methods=['GET'])
@require_auth
def api_backup_info():
    """Obtener información sobre backups existentes"""
    if not HAS_BACKUP or not backup_manager:
        return jsonify({'success': False, 'error': 'Sistema de backup no disponible'}), 503
    
    try:
        backup_info = backup_manager.get_backup_info()
        return jsonify({
            'success': True,
            'backups': backup_info
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/backup/cleanup', methods=['POST'])
@require_auth
@rate_limit
def api_cleanup_backups():
    """Limpiar backups antiguos"""
    if not HAS_BACKUP or not backup_manager:
        return jsonify({'success': False, 'error': 'Sistema de backup no disponible'}), 503
    
    try:
        data = request.get_json() or {}
        days_to_keep = data.get('days', 7)
        
        cleaned = backup_manager.cleanup_old_backups(days_to_keep=days_to_keep)
        
        return jsonify({
            'success': True,
            'message': f'Se eliminaron {cleaned} backups antiguos',
            'days_kept': days_to_keep,
            'cleaned_count': cleaned
        })
    except Exception as e:
        app.logger.error(f"Error limpiando backups: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/metrics', methods=['GET'])
@require_auth
def api_metrics():
    """Obtener métricas básicas de la aplicación"""
    try:
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'environment': FLASK_ENV,
            'uptime_seconds': None,  # Se puede implementar con time de inicio
        }
        
        # Métricas de usuarios
        if HAS_DATABASE and db:
            try:
                users = db.list_users(active_only=True)
                metrics['users'] = {
                    'total_active': len(users),
                    'total_in_db': len(db.list_users(active_only=False))
                }
            except:
                pass
        
        # Métricas de requests (básico)
        try:
            metrics['rate_limiting'] = {
                'max_requests_per_minute': MAX_REQUESTS_PER_MINUTE,
                'active_ips': len(request_log)
            }
        except:
            pass
        
        # Métricas de backups
        if HAS_BACKUP and backup_manager:
            try:
                backup_info = backup_manager.get_backup_info()
                metrics['backups'] = {
                    'total_backups': len(backup_info['daily']) + len(backup_info['weekly']) + len(backup_info['monthly']),
                    'total_size_mb': backup_info['total_size_mb']
                }
            except:
                pass
        
        return jsonify({
            'success': True,
            'metrics': metrics
        })
    except Exception as e:
        app.logger.error(f"Error obteniendo métricas: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
@rate_limit
def login():
    if request.method == 'POST':
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json()
        else:
            data = {'username': request.form.get('username'), 'password': request.form.get('password')}
        
        username = data.get('username', '').strip().lower()
        password = data.get('password', '')
        
        # Validación y sanitización de inputs
        if HAS_SECURITY and security_manager:
            if username:
                username = security_manager.sanitize_string(username, max_length=50)
            if not username or len(username) < 1:
                return jsonify({'success': False, 'error': 'Username requerido'}), 400
            if len(username) > 50:
                return jsonify({'success': False, 'error': 'Credenciales inválidas'}), 401
            
            if not password:
                return jsonify({'success': False, 'error': 'Clave requerida'}), 400
            if len(password) > 128:
                return jsonify({'success': False, 'error': 'Credenciales inválidas'}), 401
        else:
            # Validación básica
            if not username:
                return jsonify({'success': False, 'error': 'Username requerido'}), 400
            if len(username) > 50:
                return jsonify({'success': False, 'error': 'Credenciales inválidas'}), 401
            if not password:
                return jsonify({'success': False, 'error': 'Clave requerida'}), 400
            if len(password) > 128:
                return jsonify({'success': False, 'error': 'Credenciales inválidas'}), 401
        
        # Intentar autenticar desde base de datos primero
        user = None
        if HAS_DATABASE and db:
            user = db.get_user(username)
            if user and user.get('is_active'):
                if verify_password(password, user['password_hash']):
                    # Actualizar último login
                    db.update_last_login(username)
                    session['logged_in'] = True
                    session['username'] = username
                    session.permanent = True
                    # Log de login exitoso
                    try:
                        if auth_logger:
                            auth_logger.info(f"Login exitoso: {username} desde {request.remote_addr}")
                        app.logger.info(f"Usuario {username} inició sesión desde {request.remote_addr}")
                    except:
                        pass
                    return jsonify({'success': True, 'redirect': '/dashboard'})
        else:
            # Fallback: sistema en memoria
            if username in USERS and verify_password(password, USERS[username]):
                session['logged_in'] = True
                session['username'] = username
                session.permanent = True
                try:
                    if auth_logger:
                        auth_logger.info(f"Login exitoso (memoria): {username} desde {request.remote_addr}")
                except:
                    pass
                return jsonify({'success': True, 'redirect': '/dashboard'})
        
        # Credenciales inválidas
        try:
            if auth_logger:
                auth_logger.warning(f"Intento de login fallido: {username} desde {request.remote_addr}")
            app.logger.warning(f"Intento de login fallido para usuario: {username} desde {request.remote_addr}")
        except:
            pass
            return jsonify({'success': False, 'error': 'Credenciales inválidas'}), 401
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
@rate_limit
def signup():
    """Registro de nuevos usuarios"""
    global db  # Declarar db como global al inicio de la función
    if request.method == 'POST':
        try:
            if request.content_type and 'application/json' in request.content_type:
                data = request.get_json()
            else:
                data = {
                    'username': request.form.get('username'),
                    'password': request.form.get('password'),
                    'email': request.form.get('email'),
                    'security_question': request.form.get('security_question'),
                    'security_answer': request.form.get('security_answer')
                }
            
            username = data.get('username', '').strip().lower()
            password = data.get('password', '')
            email = data.get('email', '').strip().lower() if data.get('email') else ''
            security_question = data.get('security_question', '').strip()
            security_answer = data.get('security_answer', '').strip()
            
            # Validaciones mejoradas usando security_manager si está disponible
            if HAS_SECURITY and security_manager:
                # Sanitizar username
                if username:
                    username = security_manager.sanitize_string(username, max_length=50)
                else:
                    return jsonify({'success': False, 'error': 'Username requerido'}), 400
                
                # Validar longitud de username
                if len(username) < 3:
                    return jsonify({'success': False, 'error': 'Username debe tener al menos 3 caracteres'}), 400
                if len(username) > 50:
                    return jsonify({'success': False, 'error': 'Username demasiado largo (máximo 50 caracteres)'}), 400
                
                # Validar clave
                if not password:
                    return jsonify({'success': False, 'error': 'Clave requerida'}), 400
                if len(password) < 8:
                    return jsonify({'success': False, 'error': 'Clave debe tener al menos 8 caracteres'}), 400
                if len(password) > 128:
                    return safe_jsonify({'success': False, 'error': 'Contrasena demasiado larga (maximo 128 caracteres)'}), 400
                
                # Validar email si se proporciona
                if email:
                    email = security_manager.sanitize_string(email, max_length=100)
                    if not security_manager.validate_email(email):
                        return jsonify({'success': False, 'error': 'Email inválido'}), 400
            else:
                # Validación básica si security_manager no está disponible
                if not username or len(username) < 3:
                    return jsonify({'success': False, 'error': 'Username debe tener al menos 3 caracteres'}), 400
                if len(username) > 50:
                    return jsonify({'success': False, 'error': 'Username demasiado largo'}), 400
                
                if not password or len(password) < 8:
                    return jsonify({'success': False, 'error': 'Clave debe tener al menos 8 caracteres'}), 400
                if len(password) > 128:
                    return jsonify({'success': False, 'error': 'Clave demasiado larga'}), 400
                
                if email:
                    if '@' not in email or len(email) > 100:
                        return jsonify({'success': False, 'error': 'Email inválido'}), 400
            
            # Validar pregunta de seguridad (común para ambos casos)
            if not security_question or len(security_question) < 5:
                return jsonify({'success': False, 'error': 'Pregunta de seguridad requerida (minimo 5 caracteres)'}), 400
            if not security_answer or len(security_answer) < 3:
                return jsonify({'success': False, 'error': 'Respuesta de seguridad requerida (minimo 3 caracteres)'}), 400
            
            # Verificar si usuario ya existe
            if HAS_DATABASE and db:
                if db.get_user(username):
                    return jsonify({'success': False, 'error': 'Username ya existe'}), 400
                # Normalizar email para búsqueda consistente
                normalized_email = email.lower().strip() if email else None
                if normalized_email and db.get_user_by_email(normalized_email):
                    return jsonify({'success': False, 'error': 'Email ya registrado'}), 400
                
                # Crear usuario con pregunta de seguridad encriptada
                try:
                    password_hash = hash_password(password)
                    security_answer_hash = hash_password(security_answer.lower().strip())
                    
                    # Verificar que db existe
                    if not db:
                        return safe_jsonify({'success': False, 'error': 'Base de datos no disponible'}), 500
                    
                    # FORZAR RECARGA DEL MÓDULO para evitar problemas de caché en Colab
                    import importlib
                    import sys
                    if 'core.database' in sys.modules:
                        importlib.reload(sys.modules['core.database'])
                    # Re-importar db para asegurar versión actualizada
                    import core.database
                    globals()['db'] = core.database.db
                    current_db = globals()['db']
                    
                    # SOLUCIÓN DEFINITIVA: Crear usuario en dos pasos (SIEMPRE FUNCIONA)
                    # Paso 1: Crear usuario básico sin campos de seguridad
                    # Esto funciona incluso si create_user no tiene **kwargs
                    # Normalizar email a minúsculas para consistencia
                    normalized_email = email.lower().strip() if email else None
                    result = current_db.create_user(
                        username=username,
                        password_hash=password_hash,
                        email=normalized_email,
                        role='user'
                    )
                    
                    # Paso 2: Si el usuario se creó exitosamente, actualizar campos de seguridad
                    if result:
                        try:
                            # Asegurar que las columnas existen antes de actualizar
                            conn = current_db.get_connection()
                            cursor = conn.cursor()
                            try:
                                cursor.execute('ALTER TABLE users ADD COLUMN security_question TEXT')
                                conn.commit()
                            except:
                                pass
                            try:
                                cursor.execute('ALTER TABLE users ADD COLUMN security_answer_hash VARCHAR(255)')
                                conn.commit()
                            except:
                                pass
                            conn.close()
                            
                            # Actualizar campos de seguridad usando update_user
                            current_db.update_user(username, {
                                'security_question': security_question,
                                'security_answer_hash': security_answer_hash
                            })
                            
                            # Verificar que se guardaron correctamente
                            updated_user = current_db.get_user(username)
                            if updated_user:
                                if updated_user.get('security_question') and updated_user.get('security_answer_hash'):
                                    app.logger.info(f"Campos de seguridad guardados correctamente para {username}")
                                else:
                                    app.logger.warning(f"Campos de seguridad no se guardaron para {username}")
                                    # Intentar actualizar directamente con SQL
                                    conn = current_db.get_connection()
                                    cursor = conn.cursor()
                                    cursor.execute('''
                                        UPDATE users 
                                        SET security_question = ?, security_answer_hash = ?
                                        WHERE username = ?
                                    ''', (security_question, security_answer_hash, username.lower()))
                                    conn.commit()
                                    conn.close()
                                    app.logger.info(f"Campos de seguridad actualizados directamente con SQL para {username}")
                        except Exception as update_error:
                            app.logger.error(f"Error actualizando campos de seguridad: {update_error}")
                            import traceback
                            app.logger.error(traceback.format_exc())
                            # Intentar actualizar directamente con SQL como último recurso
                            try:
                                conn = current_db.get_connection()
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE users 
                                    SET security_question = ?, security_answer_hash = ?
                                    WHERE username = ?
                                ''', (security_question, security_answer_hash, username.lower()))
                                conn.commit()
                                conn.close()
                                app.logger.info(f"Campos de seguridad actualizados con SQL directo para {username}")
                            except Exception as sql_error:
                                app.logger.error(f"Error en actualización SQL directa: {sql_error}")
                                # El usuario ya está creado, continuamos de todas formas
                    if result:
                        try:
                            if auth_logger:
                                auth_logger.info(f"Usuario registrado: {username} desde {request.remote_addr}")
                            app.logger.info(f"Nuevo usuario registrado: {username} desde {request.remote_addr}")
                        except:
                            pass
                        return safe_jsonify({'success': True, 'message': 'Cuenta creada exitosamente. Redirigiendo al login...', 'redirect': '/login'})
                    else:
                        app.logger.error(f"Error al crear usuario: {username} - Usuario ya existe o error de integridad")
                        return safe_jsonify({'success': False, 'error': 'Error al crear usuario. El usuario ya existe o hay un problema con la base de datos.'}), 500
                except Exception as e:
                    app.logger.error(f"Excepcion al crear usuario {username}: {str(e)}")
                    import traceback
                    error_trace = traceback.format_exc()
                    app.logger.error(error_trace)
                    # Mostrar error detallado
                    error_message = str(e)
                    # Siempre mostrar el error real para debugging
                    return safe_jsonify({
                        'success': False, 
                        'error': f'Error al crear usuario: {error_message}'
                    }), 500
            else:
                # Fallback: sistema en memoria (solo para desarrollo)
                if username in USERS:
                    return safe_jsonify({'success': False, 'error': 'Username ya existe'}), 400
                USERS[username] = hash_password(password)
                return safe_jsonify({'success': True, 'message': 'Usuario registrado exitosamente', 'redirect': '/login'})
        except Exception as e:
            app.logger.error(f"Error en signup: {str(e)}")
            import traceback
            error_trace = traceback.format_exc()
            app.logger.error(error_trace)
            # Mostrar el error real para debugging
            error_message = str(e)
            # Siempre mostrar el error real para facilitar debugging
            return safe_jsonify({
                'success': False, 
                'error': f'Error al procesar solicitud de registro: {error_message}'
            }), 500
    
    # GET: mostrar formulario
    try:
        return render_template('signup.html')
    except Exception as e:
        # Si el template no existe, retornar HTML básico
        print(f"[ERROR] No se pudo cargar signup.html: {e}")
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Registro</title></head>
        <body>
            <h1>Registro de Usuario</h1>
            <p>El template signup.html no se encontró. Por favor, asegúrate de que el archivo existe en templates/</p>
            <p>Error: {str(e)}</p>
            <p><a href="/login">Volver al login</a></p>
        </body>
        </html>
        """, 200

@app.route('/forgot_password', methods=['GET', 'POST'])
@rate_limit
def forgot_password():
    """Recuperacion de clave - solicitar reset"""
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        email = data.get('email', '').strip().lower()
        username = data.get('username', '').strip().lower()
        
        if not email and not username:
            return safe_jsonify({'success': False, 'error': 'Proporciona email o username'}), 400
        
        # Buscar usuario - intentar por email primero, luego por username
        user = None
        if HAS_DATABASE and db:
            # Intentar buscar por email si está disponible
            if email:
                user = db.get_user_by_email(email)
                if user:
                    app.logger.info(f"Usuario encontrado por email: {email}")
                else:
                    app.logger.info(f"Usuario NO encontrado por email: {email}")
            
            # Si no se encontró por email, intentar por username
            if not user and username:
                user = db.get_user(username)
                if user:
                    app.logger.info(f"Usuario encontrado por username: {username}")
                else:
                    app.logger.info(f"Usuario NO encontrado por username: {username}")
            
            # Si ambos están disponibles y no se encontró, intentar buscar todos los usuarios para debug
            if not user and email and username:
                app.logger.warning(f"Usuario no encontrado con email={email} ni username={username}")
                # Intentar buscar sin normalización para debug
                try:
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT username, email FROM users')
                    all_users = cursor.fetchall()
                    conn.close()
                    app.logger.info(f"Usuarios en BD: {[dict(u) for u in all_users]}")
                except Exception as e:
                    app.logger.error(f"Error al listar usuarios para debug: {e}")
        
        if not user:
            # Por seguridad, no revelar si el usuario existe o no
            app.logger.warning(f"Intento de recuperación de contraseña para usuario no encontrado: email={email}, username={username}")
            return safe_jsonify({
                'success': False,
                'error': 'Usuario no encontrado. Verifica que el email o username sean correctos.'
            }), 404
        
        # SISTEMA DE PREGUNTA DE SEGURIDAD ENCRIPTADA (sin servicios externos)
        # Verificar si el usuario tiene pregunta de seguridad configurada
        security_question = user.get('security_question')
        security_answer_hash = user.get('security_answer_hash')
        
        if not security_question or not security_answer_hash:
            # Si no tiene pregunta configurada, usar método alternativo
            return safe_jsonify({
                'success': False,
                'error': 'No tienes pregunta de seguridad configurada. Contacta al administrador o configura una pregunta en tu perfil.'
            }), 400
        
        # Generar token de reset
        reset_token, expires_at = generate_reset_token()
        # Ya no necesitamos código de verificación, usamos la pregunta
        
        # Guardar token en la base de datos
        if HAS_DATABASE and db:
            db.set_reset_token(user['username'], reset_token, expires_at.isoformat())
        else:
            if not hasattr(app, 'reset_tokens'):
                app.reset_tokens = {}
            app.reset_tokens[reset_token] = {
                'username': user['username'],
                'expires_at': expires_at.isoformat()
            }
        
        # Retornar la pregunta de seguridad (sin la respuesta)
        base_url = request.host_url.rstrip('/') if hasattr(request, 'host_url') else 'http://localhost:5000'
        reset_url = f"{base_url}/reset_password?token={reset_token}"
        
        return safe_jsonify({
            'success': True,
            'message': 'Responde tu pregunta de seguridad para continuar',
            'security_question': security_question,
            'reset_token': reset_token,
            'reset_url': reset_url
        })
    
    try:
        return render_template('forgot_password.html')
    except Exception as e:
        print(f"[ERROR] No se pudo cargar forgot_password.html: {e}")
        return f"<html><body><h1>Recuperar Clave</h1><p>Template no encontrado: {str(e)}</p><a href='/login'>Volver</a></body></html>", 200

@app.route('/reset_password', methods=['GET', 'POST'])
@rate_limit
def reset_password():
    """
    Endpoint de validacion y actualizacion de clave
    GET: Muestra formulario de nueva clave (valida token)
    POST: Procesa el cambio de clave con hashing seguro (bcrypt/argon2)
    """
    token = request.args.get('token') or (request.json.get('token') if request.is_json and request.json else None)
    
    if request.method == 'POST':
        # Manejar datos de forma más robusta
        data = None
        content_type = request.content_type or ''
        
        # Intentar parsear JSON primero
        if 'application/json' in content_type:
            try:
                data = request.get_json(force=True)  # force=True para forzar parsing incluso si Content-Type no es exacto
                if data is None:
                    # Si get_json retorna None, intentar parsear manualmente
                    try:
                        import json
                        data = json.loads(request.data.decode('utf-8'))
                    except:
                        pass
            except Exception as e:
                app.logger.error(f"Error parseando JSON: {e}")
                try:
                    import json
                    data = json.loads(request.data.decode('utf-8'))
                except Exception as e2:
                    app.logger.error(f"Error parseando JSON manualmente: {e2}")
        
        # Si no hay datos JSON, usar form data
        if data is None:
            data = request.form
        
        # Logging detallado
        app.logger.info(f"reset_password POST - Content-Type: {content_type}")
        app.logger.info(f"reset_password POST - request.is_json: {request.is_json}")
        app.logger.info(f"reset_password POST - data type: {type(data)}")
        app.logger.info(f"reset_password POST - data: {str(data)[:200] if data else 'None'}")
        
        token = data.get('token', token) if data else token
        # Manejar security_answer de forma más robusta
        security_answer_raw = data.get('security_answer') if data else None
        if security_answer_raw:
            security_answer = str(security_answer_raw).strip()
        else:
            security_answer = ''
        new_password = data.get('password', '') if data else ''
        verify_only = data.get('verify_only', False) if data else False  # Solo verificar respuesta, no cambiar contraseña
        
        # Logging para debug
        app.logger.info(f"reset_password POST - token={'present' if token else 'missing'}, security_answer={'present (' + str(len(security_answer)) + ' chars)' if security_answer else 'missing'}, verify_only={verify_only}, has_password={bool(new_password)}")
        
        # Validaciones
        if not token:
            return safe_jsonify({'success': False, 'error': 'Token requerido'}), 400
        
        # Verificar y validar token
        user = None
        token_verified = False  # Flag para indicar si la respuesta ya fue verificada
        
        # Primero verificar en memoria (más rápido y confiable)
        if hasattr(app, 'reset_tokens') and token in app.reset_tokens:
            token_data = app.reset_tokens[token]
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            if datetime.now() < expires_at:
                username = token_data['username']
                user = {'username': username}
                # Verificar si la respuesta ya fue verificada (guardada en el token)
                token_verified = token_data.get('security_verified', False)
            else:
                # Token expirado
                del app.reset_tokens[token]
        
        # Si no está en memoria, verificar en base de datos
        if not user and HAS_DATABASE and db:
            user = db.verify_reset_token(token)
        
        if not user:
            return safe_jsonify({'success': False, 'error': 'Token invalido o expirado'}), 400
            
        # Obtener usuario completo para verificar pregunta de seguridad
        if HAS_DATABASE and db:
            full_user = db.get_user(user['username'])
            if not full_user:
                return safe_jsonify({'success': False, 'error': 'Usuario no encontrado'}), 400
            user = full_user
        
        # Verificar respuesta de seguridad (encriptada) - solo si no fue verificada antes
        if not token_verified:
            app.logger.info(f"Verificando respuesta de seguridad - security_answer recibido: {'SI' if security_answer else 'NO'}, longitud: {len(security_answer) if security_answer else 0}")
            
            if not security_answer or len(security_answer) < 3:
                app.logger.error(f"Respuesta de seguridad faltante o muy corta: '{security_answer}' (len={len(security_answer) if security_answer else 0})")
                app.logger.error(f"Datos recibidos: {str(data)[:500] if data else 'No data'}")
                return safe_jsonify({
                    'success': False, 
                    'error': 'Respuesta de seguridad requerida (minimo 3 caracteres)',
                    'debug': f'security_answer recibido: {"SI" if security_answer else "NO"}, longitud: {len(security_answer) if security_answer else 0}'
                }), 400
            
            security_answer_hash = user.get('security_answer_hash')
            if not security_answer_hash:
                app.logger.error(f"Usuario {user['username']} no tiene security_answer_hash configurado")
                return safe_jsonify({'success': False, 'error': 'Pregunta de seguridad no configurada'}), 400
            
            # Verificar que la respuesta coincida usando verify_password (maneja bcrypt correctamente)
            normalized_answer = security_answer.lower().strip()
            app.logger.info(f"Verificando respuesta - respuesta normalizada: '{normalized_answer}', hash almacenado: {security_answer_hash[:30] if security_answer_hash else 'None'}...")
            
            # Usar verify_password en lugar de comparar hashes directamente
            # Esto es necesario porque bcrypt genera hashes diferentes cada vez (salt aleatorio)
            if not verify_password(normalized_answer, security_answer_hash):
                app.logger.warning(f"Respuesta de seguridad incorrecta para usuario {user['username']}")
                app.logger.warning(f"Respuesta proporcionada: '{normalized_answer}'")
                app.logger.warning(f"Hash almacenado: {security_answer_hash[:30] if security_answer_hash else 'None'}...")
                return safe_jsonify({'success': False, 'error': 'Respuesta de seguridad incorrecta'}), 400
            
            app.logger.info(f"Respuesta de seguridad CORRECTA para usuario {user['username']}")
            
            # Marcar token como verificado en memoria
            if hasattr(app, 'reset_tokens') and token in app.reset_tokens:
                app.reset_tokens[token]['security_verified'] = True
                app.logger.info(f"Token marcado como verificado en memoria")
        
        # Si solo se está verificando, devolver éxito sin cambiar contraseña
        if verify_only:
            # Marcar token como verificado
            if hasattr(app, 'reset_tokens') and token in app.reset_tokens:
                app.reset_tokens[token]['security_verified'] = True
            return safe_jsonify({
                'success': True,
                'verified': True,
                'message': 'Respuesta de seguridad correcta'
            })
        
        # Si llegamos aquí, se debe cambiar la contraseña
        if not new_password:
            return safe_jsonify({'success': False, 'error': 'Nueva contrasena requerida'}), 400
        
        if len(new_password) < 8:
            return safe_jsonify({'success': False, 'error': 'La contrasena debe tener al menos 8 caracteres'}), 400
        
        if len(new_password) > 128:
            return safe_jsonify({'success': False, 'error': 'La contrasena es demasiado larga (maximo 128 caracteres)'}), 400
        
        # Actualizar clave con hashing seguro (bcrypt)
        # hash_password() ya usa bcrypt si está disponible, sino SHA-256
        try:
            new_password_hash = hash_password(new_password)
            app.logger.info(f"Hash de nueva contraseña generado para usuario {user['username']}")
        except Exception as hash_error:
            app.logger.error(f"Error generando hash de contraseña: {hash_error}")
            import traceback
            app.logger.error(traceback.format_exc())
            return safe_jsonify({'success': False, 'error': 'Error al procesar nueva contraseña'}), 500
        
        try:
            if HAS_DATABASE and db:
                # Actualizar en base de datos
                app.logger.info(f"Actualizando contraseña en base de datos para usuario {user['username']}")
                try:
                    # Actualizar contraseña
                    update_data = {
                        'password_hash': new_password_hash
                    }
                    db.update_user(user['username'], update_data)
                    app.logger.info(f"Contraseña actualizada en BD para {user['username']}")
                    
                    # Limpiar tokens de reset (opcional, puede fallar si las columnas no existen)
                    try:
                        conn = db.get_connection()
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE users 
                            SET reset_token = NULL, reset_token_expires = NULL
                            WHERE username = ?
                        ''', (user['username'].lower(),))
                        conn.commit()
                        conn.close()
                        app.logger.info(f"Tokens de reset limpiados para {user['username']}")
                    except Exception as token_cleanup_error:
                        app.logger.warning(f"No se pudieron limpiar tokens de reset (puede ser normal): {token_cleanup_error}")
                        # No es crítico, continuar
                        
                except Exception as db_error:
                    app.logger.error(f"Error en update_user: {db_error}")
                    # Intentar actualización directa con SQL como fallback
                    try:
                        conn = db.get_connection()
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE users 
                            SET password_hash = ?
                            WHERE username = ?
                        ''', (new_password_hash, user['username'].lower()))
                        conn.commit()
                        conn.close()
                        app.logger.info(f"Contraseña actualizada directamente con SQL para {user['username']}")
                    except Exception as sql_error:
                        app.logger.error(f"Error en actualización SQL directa: {sql_error}")
                        import traceback
                        app.logger.error(traceback.format_exc())
                        return safe_jsonify({'success': False, 'error': 'Error al actualizar contraseña en base de datos'}), 500
            else:
                # Fallback: actualizar en memoria (solo desarrollo)
                if user['username'] in USERS:
                    USERS[user['username']] = new_password_hash
                    app.logger.info(f"Contraseña actualizada en memoria para usuario {user['username']}")
            
            # Eliminar token usado (si está en memoria)
            if hasattr(app, 'reset_tokens') and token in app.reset_tokens:
                del app.reset_tokens[token]
                app.logger.info(f"Token de reset eliminado de memoria")
            
            # Log del cambio de clave
            try:
                if auth_logger:
                    # Sanitizar mensaje para logger (evitar problemas de encoding)
                    safe_msg = f"Contrasena actualizada para usuario: {user['username']} desde {request.remote_addr}"
                    auth_logger.info(safe_msg)
                app.logger.info(f"Contrasena actualizada exitosamente para usuario: {user['username']}")
            except Exception as log_error:
                app.logger.warning(f"Error en logging: {log_error}")
            
            return safe_jsonify({
                'success': True, 
                'message': 'Contrasena actualizada exitosamente', 
                'redirect': '/login'
            })
            
        except Exception as update_error:
            app.logger.error(f"Error al actualizar contraseña: {update_error}")
            import traceback
            app.logger.error(traceback.format_exc())
            return safe_jsonify({
                'success': False, 
                'error': f'Error al actualizar contraseña: {str(update_error)}'
            }), 500
    
    # GET: mostrar formulario con pregunta de seguridad
    if not token:
        return redirect(url_for('forgot_password'))
    
    # Obtener pregunta de seguridad del usuario
    user = None
    if hasattr(app, 'reset_tokens') and token in app.reset_tokens:
        token_data = app.reset_tokens[token]
        expires_at = datetime.fromisoformat(token_data['expires_at'])
        if datetime.now() < expires_at:
            username = token_data['username']
            if HAS_DATABASE and db:
                user = db.get_user(username)
    
    if not user and HAS_DATABASE and db:
        user_data = db.verify_reset_token(token)
        if user_data:
            user = db.get_user(user_data['username'])
    
    security_question = user.get('security_question') if user else None
    
    try:
        return render_template('reset_password.html', token=token, security_question=security_question or '')
    except Exception as e:
        print(f"[ERROR] No se pudo cargar reset_password.html: {e}")
        return f"<html><body><h1>Resetear Clave</h1><p>Template no encontrado: {str(e)}</p><a href='/login'>Volver</a></body></html>", 200

@app.route('/dashboard')
@app.route('/panel_principal')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username', 'Usuario')
    return render_template('panel_principal.html', username=username)

@app.route('/spreadsheet')
@require_auth
def spreadsheet():
    """Página de hoja de cálculo"""
    try:
        username = session.get('username', 'Usuario')
        app.logger.debug(f"Renderizando template spreadsheet.html para usuario: {username}")
        return render_template('spreadsheet.html', username=username)
    except Exception as e:
        app.logger.error(f"Error renderizando spreadsheet.html: {e}")
        import traceback
        error_trace = traceback.format_exc()
        app.logger.error(error_trace)
        
        # Intentar devolver un error más descriptivo
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': f'Error al cargar la hoja de cálculo: {str(e)}',
                'details': 'Revise los logs del servidor para más información.'
            }), 500
        else:
            # Para HTML, devolver una página de error simple
            return f"""
            <html>
            <head><title>Error - Hoja de Cálculo</title></head>
            <body style="font-family: Arial; padding: 40px; background: #0d1117; color: #c9d1d9;">
                <h1>Error al cargar la hoja de cálculo</h1>
                <p>Error: {str(e)}</p>
                <p><a href="/dashboard" style="color: #58a6ff;">Volver al Dashboard</a></p>
                <pre style="background: #161b22; padding: 20px; border-radius: 6px; overflow-x: auto;">{error_trace}</pre>
            </body>
            </html>
            """, 500

@app.route('/terminal')
@require_auth
def terminal():
    """Terminal de trading de alto nivel"""
    username = session.get('username', 'Usuario')
    return render_template('terminal.html', username=username)

@app.route('/calculadora')
@app.route('/calculadora_opciones')
def calculadora():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username', 'Usuario')
    return render_template('calculadora_opciones.html', username=username)

@app.route('/volatility_smile')
def volatility_smile():
    """Dashboard de análisis de volatilidad - Smile"""
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username', 'Usuario')
    return render_template('volatility_smile.html', username=username)

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'redirect': '/login'})

# Endpoint duplicado eliminado - usar /api/health en su lugar

# ==================== HOJAS DE CÁLCULO (SPREADSHEETS) ====================

@app.route('/api/spreadsheet/save', methods=['POST'])
@require_auth
def api_save_spreadsheet():
    """Guardar hoja de cálculo"""
    try:
        username = session.get('username')
        if not username:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
        data = request.json
        name = data.get('name', '').strip()
        spreadsheet_data = data.get('data', [])
        
        if not name:
            return jsonify({'success': False, 'error': 'Nombre requerido'}), 400
        
        if not HAS_DATABASE or not db:
            return jsonify({'success': False, 'error': 'Base de datos no disponible'}), 503
        
        success = db.save_spreadsheet(username, name, spreadsheet_data)
        
        if success:
            return jsonify({'success': True, 'message': f'Hoja "{name}" guardada exitosamente'})
        else:
            return jsonify({'success': False, 'error': 'Error al guardar'}), 500
            
    except Exception as e:
        app.logger.error(f"Error guardando spreadsheet: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/spreadsheet/list', methods=['GET'])
@require_auth
def api_list_spreadsheets():
    """Listar hojas de cálculo del usuario"""
    try:
        username = session.get('username')
        if not username:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
        if not HAS_DATABASE or not db:
            return jsonify({'success': False, 'error': 'Base de datos no disponible'}), 503
        
        spreadsheets = db.list_spreadsheets(username)
        
        return jsonify({
            'success': True,
            'spreadsheets': spreadsheets
        })
        
    except Exception as e:
        app.logger.error(f"Error listando spreadsheets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/spreadsheet/load/<name>', methods=['GET'])
@require_auth
def api_load_spreadsheet(name):
    """Cargar hoja de cálculo específica con validación robusta"""
    try:
        app.logger.info(f"Iniciando carga de spreadsheet: {name}")
        
        username = session.get('username')
        if not username:
            app.logger.warning("Intento de carga sin autenticación")
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
        if not HAS_DATABASE or not db:
            app.logger.error("Base de datos no disponible")
            return jsonify({'success': False, 'error': 'Base de datos no disponible'}), 503
        
        app.logger.debug(f"Buscando spreadsheet '{name}' para usuario '{username}'")
        data = db.get_spreadsheet(username, name)
        
        if data is None:
            app.logger.warning(f"Spreadsheet '{name}' no encontrado para usuario '{username}'")
            return jsonify({'success': False, 'error': 'Hoja no encontrada'}), 404
        
        # Validar y limpiar datos antes de retornar
        try:
            import json
            # Si data es una lista, validar que sea serializable
            if isinstance(data, (list, dict)):
                # Validar que se pueda serializar a JSON
                json.dumps(data)
                app.logger.debug(f"Datos validados exitosamente: {len(data) if isinstance(data, list) else 'dict'} elementos")
            else:
                app.logger.warning(f"Tipo de datos inesperado: {type(data)}")
                return jsonify({
                    'success': False, 
                    'error': 'Error: formato de datos inválido en la hoja de cálculo'
                }), 500
            
        except (TypeError, ValueError) as json_error:
            app.logger.error(f"Error validando datos JSON: {json_error}")
            import traceback
            app.logger.error(traceback.format_exc())
            return jsonify({
                'success': False, 
                'error': f'Error al validar datos de la hoja: {str(json_error)}'
            }), 500
        
        app.logger.info(f"Spreadsheet '{name}' cargado exitosamente")
        return jsonify({
            'success': True,
            'data': data,
            'name': name
        })
        
    except Exception as e:
        app.logger.error(f"Error inesperado cargando spreadsheet: {e}")
        import traceback
        error_trace = traceback.format_exc()
        app.logger.error(error_trace)
        return jsonify({
            'success': False, 
            'error': f'Error cargando hoja de cálculo: {str(e)}',
            'details': 'Revise los logs del servidor para más información.'
        }), 500

@app.route('/api/spreadsheet/delete/<name>', methods=['DELETE'])
@require_auth
def api_delete_spreadsheet(name):
    """Eliminar hoja de cálculo"""
    try:
        username = session.get('username')
        if not username:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
        if not HAS_DATABASE or not db:
            return jsonify({'success': False, 'error': 'Base de datos no disponible'}), 503
        
        success = db.delete_spreadsheet(username, name)
        
        if success:
            return jsonify({'success': True, 'message': f'Hoja "{name}" eliminada'})
        else:
            return jsonify({'success': False, 'error': 'Hoja no encontrada'}), 404
            
    except Exception as e:
        app.logger.error(f"Error eliminando spreadsheet: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/spreadsheet/last', methods=['GET'])
@require_auth
def api_get_last_spreadsheet():
    """Obtener la última hoja de cálculo editada por el usuario"""
    try:
        username = session.get('username')
        if not username:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
        if not HAS_DATABASE or not db:
            return jsonify({'success': False, 'error': 'Base de datos no disponible'}), 503
        
        spreadsheets = db.list_spreadsheets(username)
        
        if spreadsheets and len(spreadsheets) > 0:
            # La primera es la más reciente (ordenadas por updated_at DESC)
            last_sheet = spreadsheets[0]
            data = db.get_spreadsheet(username, last_sheet['name'])
            
            if data:
                return jsonify({
                    'success': True,
                    'name': last_sheet['name'],
                    'data': data,
                    'updated_at': last_sheet['updated_at']
                })
        
        return jsonify({'success': False, 'error': 'No hay hojas guardadas'}), 404
            
    except Exception as e:
        app.logger.error(f"Error obteniendo última spreadsheet: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tab_data/save', methods=['POST'])
@require_auth
def api_save_tab_data():
    """Guardar datos genéricos de una tab"""
    try:
        username = session.get('username')
        if not username:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
        data = request.json
        tab_name = data.get('tab_name', '').strip()
        tab_data = data.get('data', {})
        
        if not tab_name:
            return jsonify({'success': False, 'error': 'Nombre de tab requerido'}), 400
        
        if not isinstance(tab_data, dict):
            return jsonify({'success': False, 'error': 'Los datos deben ser un objeto JSON'}), 400
        
        if not HAS_DATABASE or not db:
            return jsonify({'success': False, 'error': 'Base de datos no disponible'}), 503
        
        success = db.save_tab_data(username, tab_name, tab_data)
        
        if success:
            return jsonify({'success': True, 'message': f'Datos de "{tab_name}" guardados exitosamente'})
        else:
            return jsonify({'success': False, 'error': 'Error al guardar'}), 500
            
    except Exception as e:
        app.logger.error(f"Error guardando tab_data: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tab_data/load', methods=['POST'])
@require_auth
def api_load_tab_data():
    """Cargar datos genéricos de una tab"""
    try:
        username = session.get('username')
        if not username:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
        data = request.json
        tab_name = data.get('tab_name', '').strip()
        
        if not tab_name:
            return jsonify({'success': False, 'error': 'Nombre de tab requerido'}), 400
        
        if not HAS_DATABASE or not db:
            return jsonify({'success': False, 'error': 'Base de datos no disponible'}), 503
        
        tab_data = db.get_tab_data(username, tab_name)
        
        if tab_data is not None:
            return jsonify({
                'success': True,
                'data': tab_data
            })
        else:
            return jsonify({
                'success': True,
                'data': {}  # Retornar objeto vacío si no hay datos guardados
            })
            
    except Exception as e:
        app.logger.error(f"Error cargando tab_data: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/kpis', methods=['GET'])
@require_auth
def api_admin_kpis():
    """Endpoint para obtener KPIs del sistema"""
    try:
        # Verificar que el usuario tenga permisos de admin (opcional)
        username = session.get('username')
        if not username:
            app.logger.warning(f"Intento de acceso a KPIs sin autenticación desde {request.remote_addr}")
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
        app.logger.info(f"Usuario {username} solicitando KPIs")
        kpis = {}
        
        # Estadísticas de usuarios desde base de datos
        if HAS_DATABASE and db:
            try:
                app.logger.info("Obteniendo estadísticas de usuarios desde base de datos...")
                user_stats = db.get_user_stats()
                app.logger.info(f"Estadísticas obtenidas: {len(user_stats)} campos")
                kpis.update(user_stats)
            except Exception as db_error:
                app.logger.error(f"Error obteniendo estadísticas de BD: {db_error}")
                import traceback
                app.logger.error(traceback.format_exc())
                # Continuar con fallback
                kpis = {
                    'total_users': 0,
                    'active_users': 0,
                    'inactive_users': 0,
                    'users_by_role': {},
                    'new_users_today': 0,
                    'new_users_week': 0,
                    'new_users_month': 0,
                    'logins_today': 0,
                    'logins_week': 0,
                    'logins_month': 0,
                    'verified_users': 0,
                    'users_with_security_question': 0,
                    'recent_users': [],
                    'most_active_users': []
                }
        else:
            # Fallback: estadísticas básicas desde USERS en memoria
            app.logger.info("Usando estadísticas desde USERS en memoria")
            kpis = {
                'total_users': len(USERS) if USERS else 0,
                'active_users': len(USERS) if USERS else 0,
                'inactive_users': 0,
                'users_by_role': {'user': len(USERS)} if USERS else {},
                'new_users_today': 0,
                'new_users_week': 0,
                'new_users_month': 0,
                'logins_today': 0,
                'logins_week': 0,
                'logins_month': 0,
                'verified_users': 0,
                'users_with_security_question': 0,
                'recent_users': [],
                'most_active_users': []
            }
        
        # Asegurar que todos los campos necesarios existan
        required_fields = ['total_users', 'active_users', 'inactive_users', 'users_by_role',
                          'new_users_today', 'new_users_week', 'new_users_month',
                          'logins_today', 'logins_week', 'logins_month',
                          'verified_users', 'users_with_security_question',
                          'recent_users', 'most_active_users']
        for field in required_fields:
            if field not in kpis:
                kpis[field] = 0 if field not in ['users_by_role', 'recent_users', 'most_active_users'] else ({} if field == 'users_by_role' else [])
        
        # Estadísticas adicionales del sistema
        kpis['system_info'] = {
            'has_database': HAS_DATABASE,
            'has_bcrypt': HAS_BCRYPT,
            'has_mail': HAS_MAIL and MAIL_CONFIG.get('MAIL_USERNAME'),
            'has_security': HAS_SECURITY
        }
        
        app.logger.info(f"KPIs preparados exitosamente para {username}")
        return jsonify({
            'success': True,
            'kpis': kpis,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app.logger.error(f"Error obteniendo KPIs: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc() if app.debug else None
        }), 500

# =============================================================================
# ENDPOINTS DE BACKUP
# =============================================================================

@app.route('/api/admin/backup', methods=['POST'])
@require_auth
def api_admin_backup():
    """Crear backup manual de la base de datos"""
    try:
        username = session.get('username')
        if not username:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
        from core.backup import backup_manager
        
        # Crear backup
        backup_path = backup_manager.backup_database(compress=True)
        
        if backup_path:
            app.logger.info(f"Backup manual creado por {username}: {backup_path}")
            return jsonify({
                'success': True,
                'message': 'Backup creado exitosamente',
                'backup_path': backup_path
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo crear el backup'
            }), 500
            
    except Exception as e:
        app.logger.error(f"Error creando backup manual: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/backup/info', methods=['GET'])
@require_auth
def api_admin_backup_info():
    """Obtener información de backups existentes"""
    try:
        username = session.get('username')
        if not username:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
        from core.backup import backup_manager
        
        info = backup_manager.get_backup_info()
        
        return jsonify({
            'success': True,
            'backup_info': info
        })
            
    except Exception as e:
        app.logger.error(f"Error obteniendo info de backups: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/backup/cleanup', methods=['POST'])
@require_auth
def api_admin_backup_cleanup():
    """Limpiar backups antiguos"""
    try:
        username = session.get('username')
        if not username:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
        days_to_keep = request.json.get('days_to_keep', 7) if request.is_json else 7
        
        from core.backup import backup_manager
        
        cleaned = backup_manager.cleanup_old_backups(days_to_keep=days_to_keep)
        
        app.logger.info(f"Limpieza de backups por {username}: {cleaned} archivos eliminados")
        return jsonify({
            'success': True,
            'message': f'{cleaned} backups antiguos eliminados',
            'cleaned_count': cleaned
        })
            
    except Exception as e:
        app.logger.error(f"Error limpiando backups: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/simple', methods=['GET'])
def admin_simple():
    """Ruta ultra simple sin decoradores ni templates"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Admin Simple</title>
        <style>
            body { background: #0d1117; color: #c9d1d9; padding: 40px; font-family: Arial; }
            h1 { color: #58a6ff; font-size: 32px; margin: 20px 0; }
            p { font-size: 18px; margin: 15px 0; }
            a { color: #58a6ff; font-size: 16px; text-decoration: none; display: inline-block; margin: 10px 0; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>✅ FUNCIONA - Admin Simple</h1>
        <p>Si ves esto, las rutas funcionan correctamente.</p>
        <p><strong>Rutas disponibles:</strong></p>
        <ul style="margin-left: 30px; font-size: 16px;">
            <li><a href="/admin/test">/admin/test</a> - Test con info de sesión</li>
            <li><a href="/admin/dashboard">/admin/dashboard</a> - Dashboard completo</li>
            <li><a href="/dashboard">/dashboard</a> - Dashboard principal</li>
        </ul>
    </body>
    </html>
    """
    response = app.response_class(
        response=html_content,
        status=200,
        mimetype='text/html; charset=utf-8'
    )
    return response

@app.route('/admin/test', methods=['GET'])
def admin_test():
    """Ruta de prueba simple - SIN AUTENTICACIÓN para debug"""
    try:
        username = session.get('username', 'No autenticado')
        logged_in = session.get('logged_in', False)
        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <title>Test Admin</title>
            <style>
                body {{ background: #0d1117; color: #c9d1d9; padding: 40px; font-family: Arial; }}
                h1 {{ color: #58a6ff; }}
                .info {{ background: #161b22; padding: 15px; border-radius: 6px; margin: 15px 0; }}
                a {{ color: #58a6ff; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h1>✅ Test Admin Funciona</h1>
            <div class="info">
                <p><strong>Usuario:</strong> {username}</p>
                <p><strong>Logged in:</strong> {logged_in}</p>
                <p><strong>Session:</strong> {dict(session) if session else 'No session'}</p>
            </div>
            <p>Si ves esto, las rutas funcionan correctamente.</p>
            <p><a href="/admin/dashboard">Ir al Dashboard Completo</a></p>
            <p><a href="/dashboard">Volver al Dashboard Principal</a></p>
        </body>
        </html>
        """, 200
    except Exception as e:
        return f"<html><body><h1>Error en test</h1><p>{str(e)}</p></body></html>", 500

@app.route('/admin/dashboard', methods=['GET'])
def admin_dashboard():
    """Dashboard de administración con KPIs - VERSIÓN INLINE COMPLETA"""
    try:
        # Verificar autenticación
        if 'logged_in' not in session:
            return """
            <!DOCTYPE html>
            <html><head><meta charset="UTF-8"><title>No Autenticado</title></head>
            <body style="background: #0d1117; color: #c9d1d9; padding: 40px;">
                <h1 style="color: #f85149;">No autenticado</h1>
                <p><a href="/login" style="color: #58a6ff;">Ir al Login</a></p>
            </body></html>
            """, 401
        
        username = session.get('username', 'Usuario')
        app.logger.info(f"Usuario {username} accediendo a admin dashboard")
        
        # Retornar HTML completo inline con JavaScript para cargar KPIs
        html_content = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Administración - KPIs</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: Arial, sans-serif; background: #0d1117; color: #c9d1d9; min-height: 100vh; }}
        .header {{ background: #161b22; border-bottom: 1px solid #21262d; padding: 20px 40px; display: flex; justify-content: space-between; align-items: center; }}
        .header h1 {{ color: #58a6ff; font-size: 24px; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 30px 20px; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .kpi-card {{ background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 20px; }}
        .kpi-card-value {{ font-size: 32px; font-weight: 700; color: #58a6ff; margin: 10px 0; }}
        .kpi-card-title {{ color: #8b949e; font-size: 14px; }}
        .loading {{ text-align: center; padding: 40px; color: #8b949e; }}
        .error {{ background: #da3633; color: white; padding: 15px; border-radius: 6px; margin: 20px 0; }}
        .btn {{ padding: 8px 16px; border-radius: 6px; border: 1px solid #30363d; background: #21262d; color: #c9d1d9; cursor: pointer; text-decoration: none; display: inline-block; }}
        .btn:hover {{ background: #30363d; border-color: #58a6ff; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Dashboard de Administración</h1>
        <div>
            <span style="color: #8b949e;">{username}</span>
            <a href="/dashboard" class="btn" style="margin-left: 15px;">Dashboard Principal</a>
            <button class="btn" onclick="logout()" style="margin-left: 10px;">Salir</button>
        </div>
    </div>
    
    <div class="container">
        <div id="loading" class="loading">
            <p>🔄 Cargando KPIs...</p>
        </div>
        
        <div id="error-container" style="display: none;"></div>
        
        <div id="dashboard-content" style="display: none;">
            <div class="kpi-grid" id="kpi-grid"></div>
            <div style="background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 20px; margin-top: 20px;">
                <h3 style="color: #58a6ff; margin-bottom: 15px;">📋 Últimos Usuarios</h3>
                <div id="users-list"></div>
            </div>
        </div>
    </div>
    
    <script>
        async function loadKPIs() {{
            const loading = document.getElementById('loading');
            const content = document.getElementById('dashboard-content');
            const errorContainer = document.getElementById('error-container');
            
            loading.style.display = 'block';
            content.style.display = 'none';
            errorContainer.style.display = 'none';
            
            try {{
                const response = await fetch('/api/admin/kpis', {{
                    method: 'GET',
                    headers: {{ 'Content-Type': 'application/json' }},
                    credentials: 'include'
                }});
                
                const data = await response.json();
                
                if (!response.ok || !data.success) {{
                    throw new Error(data.error || 'Error al cargar KPIs');
                }}
                
                displayKPIs(data.kpis);
                loading.style.display = 'none';
                content.style.display = 'block';
                
            }} catch (error) {{
                console.error('Error:', error);
                loading.style.display = 'none';
                errorContainer.innerHTML = '<div class="error">Error: ' + error.message + '</div>';
                errorContainer.style.display = 'block';
            }}
        }}
        
        function displayKPIs(kpis) {{
            const kpiGrid = document.getElementById('kpi-grid');
            
            // Formatear moneda
            const formatCurrency = (val) => {{
                if (!val || val === 0) return '$0.00';
                return '$' + parseFloat(val).toFixed(2);
            }};
            
            // Formatear porcentaje
            const formatPercent = (val) => {{
                if (!val || val === 0) return '0%';
                return parseFloat(val).toFixed(1) + '%';
            }};
            
            kpiGrid.innerHTML = `
                <!-- MÉTRICAS DE USUARIOS -->
                <div class="kpi-card">
                    <div class="kpi-card-title">👥 Total Usuarios</div>
                    <div class="kpi-card-value">${{kpis.total_users || 0}}</div>
                    <div class="kpi-card-title">${{kpis.active_users || 0}} activos | ${{kpis.inactive_users || 0}} inactivos</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-card-title">🆕 Nuevos Usuarios (Hoy)</div>
                    <div class="kpi-card-value">${{kpis.new_users_today || 0}}</div>
                    <div class="kpi-card-title">${{kpis.new_users_week || 0}} esta semana | ${{kpis.new_users_month || 0}} este mes</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-card-title">🔐 Logins Hoy</div>
                    <div class="kpi-card-value">${{kpis.logins_today || 0}}</div>
                    <div class="kpi-card-title">${{kpis.logins_week || 0}} esta semana | ${{kpis.logins_month || 0}} este mes</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-card-title">✅ Email Verificado</div>
                    <div class="kpi-card-value">${{kpis.verified_users || 0}}</div>
                    <div class="kpi-card-title">${{kpis.unverified_users || 0}} sin verificar</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-card-title">🔒 Seguridad Configurada</div>
                    <div class="kpi-card-value">${{kpis.users_with_security_question || 0}}</div>
                    <div class="kpi-card-title">${{kpis.users_without_security_question || 0}} sin configurar</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-card-title">📊 Tasa de Retención (7d)</div>
                    <div class="kpi-card-value">${{formatPercent(kpis.retention_rate_7d)}}</div>
                    <div class="kpi-card-title">${{kpis.inactive_users_30_days || 0}} inactivos 30+ días</div>
                </div>
                
                <!-- MÉTRICAS DE SESIONES -->
                <div class="kpi-card">
                    <div class="kpi-card-title">🌐 Sesiones Activas</div>
                    <div class="kpi-card-value">${{kpis.active_sessions || 0}}</div>
                    <div class="kpi-card-title">${{kpis.sessions_today || 0}} hoy | ${{kpis.sessions_week || 0}} esta semana</div>
                </div>
                
                <!-- MÉTRICAS DE PORTFOLIOS -->
                <div class="kpi-card">
                    <div class="kpi-card-title">💼 Portfolios Guardados</div>
                    <div class="kpi-card-value">${{kpis.total_portfolios || 0}}</div>
                    <div class="kpi-card-title">${{kpis.users_with_portfolio || 0}} usuarios | ${{formatPercent(kpis.portfolio_adoption_rate)}} adopción</div>
                </div>
                
                <!-- MÉTRICAS DE ESTRATEGIAS -->
                <div class="kpi-card">
                    <div class="kpi-card-title">📈 Estrategias Guardadas</div>
                    <div class="kpi-card-value">${{kpis.total_strategies || 0}}</div>
                    <div class="kpi-card-title">${{kpis.users_with_strategies || 0}} usuarios | ${{kpis.strategies_week || 0}} esta semana</div>
                </div>
                
                <!-- MÉTRICAS DE SUSCRIPCIONES -->
                <div class="kpi-card">
                    <div class="kpi-card-title">💳 Suscripciones Activas</div>
                    <div class="kpi-card-value">${{kpis.active_subscriptions || 0}}</div>
                    <div class="kpi-card-title">${{formatPercent(kpis.subscription_conversion_rate)}} conversión | ${{kpis.subscriptions_month || 0}} este mes</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-card-title">⚠️ Suscripciones Expiradas</div>
                    <div class="kpi-card-value">${{kpis.expired_subscriptions || 0}}</div>
                    <div class="kpi-card-title">Requieren renovación</div>
                </div>
                
                <!-- MÉTRICAS DE PAGOS -->
                <div class="kpi-card">
                    <div class="kpi-card-title">💰 Ingresos Totales</div>
                    <div class="kpi-card-value">${{formatCurrency(kpis.total_revenue_usd)}}</div>
                    <div class="kpi-card-title">${{formatCurrency(kpis.revenue_month_usd)}} este mes | ${{formatCurrency(kpis.revenue_week_usd)}} esta semana</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-card-title">💵 Pagos Totales</div>
                    <div class="kpi-card-value">${{kpis.total_payments || 0}}</div>
                    <div class="kpi-card-title">${{kpis.payments_month || 0}} este mes | ${{kpis.pending_payments || 0}} pendientes</div>
                </div>
            `;
            
            // Mostrar usuarios recientes
            const usersList = document.getElementById('users-list');
            if (kpis.recent_users && kpis.recent_users.length > 0) {{
                usersList.innerHTML = '<ul style="list-style: none; padding: 0;">' + 
                    kpis.recent_users.map(u => {{
                        const created = u.created_at ? new Date(u.created_at).toLocaleDateString('es-AR') : 'N/A';
                        const lastLogin = u.last_login ? new Date(u.last_login).toLocaleDateString('es-AR') : 'Nunca';
                        const status = u.is_active ? '✅' : '❌';
                        return `<li style="padding: 10px; border-bottom: 1px solid #21262d; display: flex; justify-content: space-between;">
                            <span>${{status}} <strong>${{u.username}}</strong> - ${{u.email || 'N/A'}} - ${{u.role}}</span>
                            <span style="color: #8b949e; font-size: 12px;">Creado: ${{created}} | Último login: ${{lastLogin}}</span>
                        </li>`;
                    }}).join('') +
                    '</ul>';
            }} else {{
                usersList.innerHTML = '<p style="color: #8b949e;">No hay usuarios registrados</p>';
            }}
            
            // Agregar sección de usuarios más activos si existe
            if (kpis.most_active_users && kpis.most_active_users.length > 0) {{
                const activeSection = document.createElement('div');
                activeSection.style.cssText = 'background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 20px; margin-top: 20px;';
                activeSection.innerHTML = `
                    <h3 style="color: #58a6ff; margin-bottom: 15px;">🔥 Usuarios Más Activos</h3>
                    <ul style="list-style: none; padding: 0;">
                        ${{kpis.most_active_users.map(u => {{
                            const lastLogin = u.last_login ? new Date(u.last_login).toLocaleString('es-AR') : 'Nunca';
                            return `<li style="padding: 10px; border-bottom: 1px solid #21262d;">
                                <strong>${{u.username}}</strong> - ${{u.email || 'N/A'}} - ${{u.role}}<br>
                                <small style="color: #8b949e;">Último login: ${{lastLogin}}</small>
                            </li>`;
                        }}).join('')}}
                    </ul>
                `;
                document.getElementById('dashboard-content').appendChild(activeSection);
            }}
            
            // Agregar sección de suscripciones por plan si existe
            if (kpis.subscriptions_by_plan && Object.keys(kpis.subscriptions_by_plan).length > 0) {{
                const subsSection = document.createElement('div');
                subsSection.style.cssText = 'background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 20px; margin-top: 20px;';
                subsSection.innerHTML = `
                    <h3 style="color: #58a6ff; margin-bottom: 15px;">📊 Suscripciones por Plan</h3>
                    <ul style="list-style: none; padding: 0;">
                        ${{Object.entries(kpis.subscriptions_by_plan).map(([plan, count]) => `
                            <li style="padding: 10px; border-bottom: 1px solid #21262d;">
                                <strong>${{plan.toUpperCase()}}</strong>: ${{count}} usuarios
                            </li>
                        `).join('')}}
                    </ul>
                `;
                document.getElementById('dashboard-content').appendChild(subsSection);
            }}
        }}
        
        function logout() {{
            fetch('/logout', {{ method: 'POST', credentials: 'include' }})
                .then(() => window.location.href = '/login');
        }}
        
        // Cargar al iniciar
        loadKPIs();
        setInterval(loadKPIs, 60000);
    </script>
</body>
</html>
        """
        
        # Retornar con headers explícitos para asegurar que se muestre
        response = app.response_class(
            response=html_content,
            status=200,
            mimetype='text/html; charset=utf-8'
        )
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        app.logger.info(f"Retornando dashboard HTML, longitud: {len(html_content)} caracteres")
        return response
        
    except Exception as e:
        app.logger.error(f"Error en admin_dashboard: {e}")
        import traceback
        error_trace = traceback.format_exc()
        app.logger.error(error_trace)
        return f"""
        <html>
        <head><title>Admin Dashboard - Error</title></head>
        <body style="background: #0d1117; color: #c9d1d9; padding: 40px; font-family: Arial;">
            <h1 style="color: #f85149;">❌ Error al cargar dashboard</h1>
            <p><strong>Error:</strong> {str(e)}</p>
            <details style="margin-top: 20px;">
                <summary style="cursor: pointer; color: #58a6ff;">Ver detalles técnicos</summary>
                <pre style="background: #161b22; padding: 15px; border-radius: 6px; overflow: auto; margin-top: 10px;">{error_trace}</pre>
            </details>
            <p style="margin-top: 20px;"><a href="/dashboard" style="color: #58a6ff;">Volver al Dashboard</a></p>
        </body>
        </html>
        """, 500

@app.route('/api/black-scholes', methods=['POST'])
@require_auth
def api_black_scholes():
    if not MODULES_LOADED:
        return jsonify({'success': False, 'error': 'Módulos no cargados'}), 503
    try:
        data = request.json
        resultado = black_scholes_advanced(
            data.get('parametro', 'prima'),
            float(data['s']),
            float(data['k']),
            float(data['T']),
            float(data.get('r', 0.05)),
            float(data.get('q', 0.0)),
            float(data['sigma']),
            data.get('call_put', 'call'),
            data.get('tipo_subyacente', 'accion'),
            data.get('estilo_liquidacion', '')
        )
        return jsonify({
            'success': True,
            'model': 'Black-Scholes',
            'resultado': float(resultado)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/greeks', methods=['POST'])
@require_auth
def api_greeks():
    if not MODULES_LOADED:
        return jsonify({'success': False, 'error': 'Módulos no cargados'}), 503
    try:
        data = request.json
        griegas = calcular_griegas_completas(
            data['modelo'],
            float(data['s']),
            float(data['k']),
            float(data['T']),
            float(data.get('r', 0.05)),
            float(data.get('q', 0.0)),
            float(data['sigma']),
            data.get('call_put', 'call'),
            data.get('tipo_subyacente', 'accion'),
            data.get('estilo_liquidacion', ''),
            data.get('euro_amer', 'europea'),
            int(data.get('n', 100))
        )
        
        for key, value in griegas.items():
            if hasattr(value, 'item'):
                griegas[key] = value.item()
            else:
                griegas[key] = float(value)
        
        return jsonify({'success': True, 'greeks': griegas})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/escenarios', methods=['POST'])
@require_auth
def api_escenarios():
    if not MODULES_LOADED:
        return jsonify({'success': False, 'error': 'Módulos no cargados'}), 503
    try:
        data = request.json
        escenarios = analizar_escenarios(
            data['modelo'],
            float(data['s']),
            float(data['k']),
            float(data['T']),
            float(data.get('r', 0.05)),
            float(data.get('q', 0.0)),
            float(data['sigma']),
            data.get('call_put', 'call'),
            data.get('movimientos_pct', list(range(-10, 11, 2))),
            data.get('tipo_subyacente', 'accion'),
            data.get('estilo_liquidacion', ''),
            data.get('euro_amer', 'europea'),
            int(data.get('n', 100))
        )
        
        resultados = []
        for row in escenarios:
            resultados.append({
                'movimiento_pct': float(row[0]),
                'spot_nuevo': float(row[1]),
                'prima_nueva': float(row[2]),
                'variacion_abs': float(row[3]),
                'variacion_pct': float(row[4])
            })
        
        return jsonify({'success': True, 'escenarios': resultados})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/calculate_option', methods=['POST'])
@require_auth
def api_calculate_option():
    """Endpoint unificado para calcular opciones con todos los griegas"""
    if not MODULES_LOADED:
        return jsonify({'success': False, 'error': 'Módulos no cargados'}), 503
    
    try:
        data = request.json
        model = data.get('model', 'black-scholes')
        option_type = data.get('option_type', 'call')
        spot = float(data.get('spot'))
        strike = float(data.get('strike'))
        maturity = float(data.get('maturity'))
        volatility = float(data.get('volatility')) / 100  # Convertir % a decimal
        risk_free = float(data.get('risk_free_rate', 5)) / 100
        asset_type = data.get('asset_type', 'stock')
        binomial_steps = int(data.get('binomial_steps', 100))
        
        # Estilo de liquidación para futuros
        estilo_liquidacion = ''
        if asset_type == 'future':
            estilo_liquidacion = data.get('settlement_style', 'equity_style')
            if estilo_liquidacion not in ['futures_style', 'equity_style', 'matba_rofex_style']:
                estilo_liquidacion = 'equity_style'  # Default
        
        # Mapear nombres de modelos
        model_map = {
            'black-scholes': 'bs',
            'binomial': 'binomial',
            'bs93': 'bs93'
        }
        model_name = model_map.get(model, 'bs')
        
        # Calcular griegas completas
        griegas = calcular_griegas_completas(
            model_name,
            spot,
            strike,
            maturity / 365,  # Convertir días a años
            risk_free,
            0.0,  # q (dividendos)
            volatility,
            option_type,
            'accion' if asset_type == 'stock' else 'futuro',
            estilo_liquidacion,
            'europea',  # euro_amer
            binomial_steps  # n (pasos binomial)
        )
        
        # Convertir numpy a float
        for key, value in griegas.items():
            if hasattr(value, 'item'):
                griegas[key] = float(value.item())
            else:
                griegas[key] = float(value)
        
        # Agregar alias 'theta' para compatibilidad con la interfaz
        if 'theta_anual' in griegas:
            griegas['theta'] = griegas['theta_anual']
        
        # Asegurar que gammap esté disponible (alias si viene como gamma_p)
        if 'gammap' not in griegas and 'gamma_p' in griegas:
            griegas['gammap'] = griegas['gamma_p']
        elif 'gammap' not in griegas and 'gamma' in griegas:
            # Calcular gammap si no está presente
            griegas['gammap'] = griegas['gamma'] * spot / 100
        
        # Calcular precio de la opción usando Delta como aproximación inicial o calculando directamente
        # Para simplificar, usamos black_scholes_advanced para obtener el precio
        price = black_scholes_advanced(
            'prima',
            spot,
            strike,
            maturity / 365,
            risk_free,
            0.0,
            volatility,
            option_type,
            'accion' if asset_type == 'stock' else 'futuro',
            estilo_liquidacion
        )
        
        # Calcular theta decay real
        theta_decay_data = []
        for d in range(1, int(maturity) + 1, 2):
            T_restante = (maturity - d) / 365
            if T_restante <= 0:
                theta_decay_data.append({'days': d, 'premium': 0})
            else:
                try:
                    if model_name == 'bs':
                        p = black_scholes_advanced("prima", spot, strike, T_restante, risk_free, 0.0,
                                                  volatility, option_type, 
                                                  'accion' if asset_type == 'stock' else 'futuro', 
                                                  estilo_liquidacion)
                    elif model_name == 'binomial':
                        p = binomial_op_val("prima", spot, strike, T_restante, risk_free, 0.0,
                                          volatility, option_type, 'europea', binomial_steps,
                                          'accion' if asset_type == 'stock' else 'futuro', 
                                          estilo_liquidacion)
                    elif model_name == 'bs93':
                        p = bs93_amer("prima", spot, strike, T_restante, risk_free, 0.0,
                                    volatility, option_type, 
                                    'accion' if asset_type == 'stock' else 'futuro')
                    theta_decay_data.append({'days': d, 'premium': float(p)})
                except:
                    theta_decay_data.append({'days': d, 'premium': 0})
        
        # Calcular escenarios reales (movimientos -20% a +20%)
        scenarios_data = []
        movements = list(range(-20, 21, 1))
        for mov in movements:
            s_nuevo = spot * (1 + mov / 100)
            try:
                if model_name == 'bs':
                    prima_nueva = black_scholes_advanced("prima", s_nuevo, strike, maturity / 365, risk_free, 0.0,
                                                        volatility, option_type, 
                                                        'accion' if asset_type == 'stock' else 'futuro', 
                                                        estilo_liquidacion)
                    delta_nuevo = black_scholes_advanced("delta", s_nuevo, strike, maturity / 365, risk_free, 0.0,
                                                        volatility, option_type, 
                                                        'accion' if asset_type == 'stock' else 'futuro', 
                                                        estilo_liquidacion)
                    gamma_nuevo = black_scholes_advanced("gamma", s_nuevo, strike, maturity / 365, risk_free, 0.0,
                                                        volatility, option_type, 
                                                        'accion' if asset_type == 'stock' else 'futuro', 
                                                        estilo_liquidacion)
                elif model_name == 'binomial':
                    prima_nueva = binomial_op_val("prima", s_nuevo, strike, maturity / 365, risk_free, 0.0,
                                                 volatility, option_type, 'europea', binomial_steps,
                                                 'accion' if asset_type == 'stock' else 'futuro', 
                                                 estilo_liquidacion)
                    delta_nuevo = binomial_op_val("delta", s_nuevo, strike, maturity / 365, risk_free, 0.0,
                                                 volatility, option_type, 'europea', binomial_steps,
                                                 'accion' if asset_type == 'stock' else 'futuro', 
                                                 estilo_liquidacion)
                    gamma_nuevo = binomial_op_val("gamma", s_nuevo, strike, maturity / 365, risk_free, 0.0,
                                                 volatility, option_type, 'europea', binomial_steps,
                                                 'accion' if asset_type == 'stock' else 'futuro', 
                                                 estilo_liquidacion)
                elif model_name == 'bs93':
                    prima_nueva = bs93_amer("prima", s_nuevo, strike, maturity / 365, risk_free, 0.0,
                                           volatility, option_type, 
                                           'accion' if asset_type == 'stock' else 'futuro')
                    delta_nuevo = bs93_amer("delta", s_nuevo, strike, maturity / 365, risk_free, 0.0,
                                           volatility, option_type, 
                                           'accion' if asset_type == 'stock' else 'futuro')
                    gamma_nuevo = bs93_amer("gamma", s_nuevo, strike, maturity / 365, risk_free, 0.0,
                                           volatility, option_type, 
                                           'accion' if asset_type == 'stock' else 'futuro')
                
                variacion_abs = prima_nueva - float(price)
                # Delta = dP/dS, entonces ΔP = Delta × ΔS
                # ΔS = spot × (mov/100), entonces ΔP = Delta × spot × (mov/100)
                delta_S = spot * (mov / 100)  # Cambio absoluto en precio
                aprox_lineal = griegas['delta'] * delta_S
                # Gamma = d²P/dS², entonces término cuadrático = 0.5 × Gamma × (ΔS)²
                aprox_taylor = aprox_lineal + 0.5 * griegas['gamma'] * (delta_S ** 2)
                
                scenarios_data.append({
                    'mov': mov,
                    'spot': float(s_nuevo),
                    'prima': float(prima_nueva),
                    'delta': float(delta_nuevo),
                    'gamma': float(gamma_nuevo),
                    'variacion': float(variacion_abs),
                    'aprox_lineal': float(aprox_lineal),
                    'aprox_taylor': float(aprox_taylor),
                    'error_lineal': abs(float(variacion_abs) - float(aprox_lineal)),
                    'error_taylor': abs(float(variacion_abs) - float(aprox_taylor))
                })
            except:
                scenarios_data.append({
                    'mov': mov,
                    'spot': float(s_nuevo),
                    'prima': 0,
                    'delta': 0,
                    'gamma': 0,
                    'variacion': 0,
                    'aprox_lineal': 0,
                    'aprox_taylor': 0,
                    'error_lineal': 0,
                    'error_taylor': 0
                })
        
        return jsonify({
            'success': True,
            'data': {
                'price': float(price),
                'spot': spot,
                'strike': strike,
                'greeks': griegas,
                'model': model,
                'option_type': option_type,
                'asset_type': asset_type,
                'binomial_steps': binomial_steps,
                'maturity': maturity,
                'volatility': volatility * 100,
                'risk_free_rate': risk_free * 100,
                'theta_decay': theta_decay_data,
                'scenarios': scenarios_data
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

# Portfolio endpoints
if HAS_PORTFOLIO:
    # Portfolios: usar DB si está disponible, sino memoria
    if not HAS_DATABASE:
        user_portfolios = {}
    
    # Cache de portfolios en memoria para evitar recrear en cada request
    if not HAS_DATABASE:
        user_portfolios = {}
    else:
        # Cache también cuando hay DB para mejor rendimiento
        user_portfolios = {}
    
    def get_user_portfolio():
        """Get or create portfolio for current user"""
        username = session.get('username', 'default')
        
        # Usar cache si existe y está actualizado
        if username in user_portfolios:
            return user_portfolios[username]
        
        pricer = OptionPricer()
        portfolio = Portfolio(pricer)
        
        if HAS_DATABASE and db:
            # Cargar desde DB
            portfolio_data = db.get_portfolio(username)
            
            if portfolio_data:
                # Restaurar posiciones desde datos guardados
                for pos_data in portfolio_data.get('positions', []):
                    try:
                        pos = OptionPosition(**pos_data)
                        portfolio.add_position(pos)
                    except Exception as e:
                        app.logger.warning(f"Error restaurando posición: {e}")
        
        # Guardar en cache
        user_portfolios[username] = portfolio
        return portfolio
    
    def save_user_portfolio():
        """Guardar portfolio del usuario"""
        if HAS_DATABASE and db:
            username = session.get('username', 'default')
            portfolio = get_user_portfolio()
            
            # Guardar posiciones
            positions_data = []
            for pos in portfolio.positions:
                positions_data.append({
                    'symbol': pos.symbol,
                    'strike': pos.strike,
                    'expiration_days': pos.expiration_days,
                    'option_type': pos.option_type,
                    'quantity': pos.quantity,
                    'market_price': pos.market_price,
                    'spot': pos.spot,
                    'risk_free_rate': pos.risk_free_rate,
                    'volatility': pos.volatility,
                    'asset_type': pos.asset_type,
                    'dividend_yield': pos.dividend_yield,
                    'settlement_style': pos.settlement_style,
                    'model': pos.model,
                    'binomial_steps': pos.binomial_steps
                })
            db.save_portfolio(username, {'positions': positions_data})
    
    @app.route('/api/portfolio/strategies', methods=['GET'])
    @require_auth
    def api_get_strategies():
        """Get list of available strategies"""
        try:
            strategies = StrategyBuilder.get_strategy_list()
            return jsonify({'success': True, 'strategies': strategies})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/api/portfolio/add_strategy', methods=['POST'])
    @require_auth
    def api_add_strategy():
        """Add a strategy to portfolio"""
        if not HAS_PORTFOLIO:
            return jsonify({'success': False, 'error': 'Portfolio modules not available'}), 503
        
        try:
            data = request.json
            strategy_type = data.get('strategy_type')
            portfolio = get_user_portfolio()
            
            # Helper function para convertir market_prices de lista a tupla
            def convert_market_prices(market_prices, expected_length=None):
                """Convert market_prices from list to tuple if needed"""
                if market_prices is None:
                    return None
                if isinstance(market_prices, list):
                    if expected_length and len(market_prices) >= expected_length:
                        return tuple(market_prices[:expected_length])
                    return tuple(market_prices)
                if isinstance(market_prices, tuple):
                    return market_prices
                return None
            
            # Common parameters
            spot = float(data.get('spot'))
            risk_free_rate = float(data.get('risk_free_rate', 5)) / 100
            volatility = float(data.get('volatility')) / 100
            asset_type = data.get('asset_type', 'stock')
            dividend_yield = float(data.get('dividend_yield', 0)) / 100
            model = data.get('model', 'black-scholes')
            binomial_steps = int(data.get('binomial_steps', 100))
            quantity = int(data.get('quantity', 1))
            
            # Estilo de liquidación para futuros
            settlement_style = ''
            if asset_type == 'future':
                settlement_style = data.get('settlement_style', 'equity_style')
                if settlement_style not in ['futures_style', 'equity_style', 'matba_rofex_style']:
                    settlement_style = 'equity_style'  # Default
            
            # Create strategy based on type
            if strategy_type == 'single':
                positions = [StrategyBuilder.create_single_option(
                    spot=spot,
                    strike=float(data.get('strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    option_type=data.get('option_type', 'call'),
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_price=float(data.get('market_price', 0)),
                    direction=data.get('direction', 'long'),
                    settlement_style=settlement_style
                )]
            elif strategy_type == 'bull_call_spread':
                positions = StrategyBuilder.create_bull_call_spread(
                    spot=spot,
                    lower_strike=float(data.get('lower_strike')),
                    upper_strike=float(data.get('upper_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 2),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'bear_call_spread':
                positions = StrategyBuilder.create_bear_call_spread(
                    spot=spot,
                    lower_strike=float(data.get('lower_strike')),
                    upper_strike=float(data.get('upper_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 2),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'bull_put_spread':
                positions = StrategyBuilder.create_bull_put_spread(
                    spot=spot,
                    lower_strike=float(data.get('lower_strike')),
                    upper_strike=float(data.get('upper_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 2),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'bear_put_spread':
                positions = StrategyBuilder.create_bear_put_spread(
                    spot=spot,
                    lower_strike=float(data.get('lower_strike')),
                    upper_strike=float(data.get('upper_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 2),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'straddle':
                positions = StrategyBuilder.create_straddle(
                    spot=spot,
                    strike=float(data.get('strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 2),
                    direction=data.get('direction', 'long'),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'strangle':
                positions = StrategyBuilder.create_strangle(
                    spot=spot,
                    lower_strike=float(data.get('lower_strike')),
                    upper_strike=float(data.get('upper_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 2),
                    direction=data.get('direction', 'long'),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'iron_condor':
                positions = StrategyBuilder.create_iron_condor(
                    spot=spot,
                    lower_put_strike=float(data.get('lower_put_strike')),
                    upper_put_strike=float(data.get('upper_put_strike')),
                    lower_call_strike=float(data.get('lower_call_strike')),
                    upper_call_strike=float(data.get('upper_call_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 4),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'calendar_spread':
                positions = StrategyBuilder.create_calendar_spread(
                    spot=spot,
                    strike=float(data.get('strike')),
                    short_expiration_days=float(data.get('short_expiration_days')),
                    long_expiration_days=float(data.get('long_expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    option_type=data.get('option_type', 'call'),
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 2),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'delta_hedge':
                positions = StrategyBuilder.create_delta_hedge(
                    spot=spot,
                    option_strike=float(data.get('strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    option_type=data.get('option_type', 'call'),
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    option_quantity=quantity,
                    market_price=float(data.get('market_price', 0)),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'delta_gamma_hedge':
                positions = StrategyBuilder.create_delta_gamma_hedge(
                    spot=spot,
                    option_strike=float(data.get('strike')),
                    hedge_option_strike=float(data.get('hedge_option_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    option_type=data.get('option_type', 'call'),
                    hedge_option_type=data.get('hedge_option_type'),
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    option_quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 2),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'call_butterfly':
                positions = StrategyBuilder.create_call_butterfly(
                    spot=spot,
                    lower_strike=float(data.get('lower_strike')),
                    middle_strike=float(data.get('middle_strike')),
                    upper_strike=float(data.get('upper_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 3),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'put_butterfly':
                positions = StrategyBuilder.create_put_butterfly(
                    spot=spot,
                    lower_strike=float(data.get('lower_strike')),
                    middle_strike=float(data.get('middle_strike')),
                    upper_strike=float(data.get('upper_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 3),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'protective_put':
                positions = StrategyBuilder.create_protective_put(
                    spot=spot,
                    put_strike=float(data.get('put_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 2),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'protective_call':
                positions = StrategyBuilder.create_protective_call(
                    spot=spot,
                    call_strike=float(data.get('call_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 2),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'covered_call':
                positions = StrategyBuilder.create_covered_call(
                    spot=spot,
                    call_strike=float(data.get('call_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 2),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'covered_put':
                positions = StrategyBuilder.create_covered_put(
                    spot=spot,
                    put_strike=float(data.get('put_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 2),
                    settlement_style=settlement_style
                )
            elif strategy_type == 'collar':
                positions = StrategyBuilder.create_collar(
                    spot=spot,
                    put_strike=float(data.get('put_strike')),
                    call_strike=float(data.get('call_strike')),
                    expiration_days=float(data.get('expiration_days')),
                    risk_free_rate=risk_free_rate,
                    volatility=volatility,
                    asset_type=asset_type,
                    dividend_yield=dividend_yield,
                    model=model,
                    binomial_steps=binomial_steps,
                    quantity=quantity,
                    market_prices=convert_market_prices(data.get('market_prices'), 3),
                    settlement_style=settlement_style
                )
            else:
                return jsonify({'success': False, 'error': f'Unknown strategy: {strategy_type}'}), 400
            
            # Verificar límites de suscripción
            if HAS_SUBSCRIPTION:
                username = session.get('username', 'default')
                current_count = len(portfolio.positions)
                can_add, error_msg = subscription_manager.can_add_strategy(username, current_count)
                if not can_add:
                    return jsonify({'success': False, 'error': error_msg, 'subscription_required': True}), 403
            
            # Add all positions to portfolio
            for pos in positions:
                portfolio.add_position(pos)
            
            # Actualizar cache
            username = session.get('username', 'default')
            user_portfolios[username] = portfolio
            
            # Guardar portfolio en DB
            if HAS_DATABASE and db:
                save_user_portfolio()
            
            # Retornar summary actualizado para que el frontend pueda actualizar inmediatamente
            summary = portfolio.get_portfolio_summary()
            result = {
                'success': True,
                'message': f'Added {len(positions)} positions',
                'portfolio': {
                    'num_positions': summary['num_positions'],
                    'market_value': float(summary['market_value']),
                    'theoretical_value': float(summary['theoretical_value']),
                    'unrealized_pnl': float(summary['unrealized_pnl']),
                    'aggregate_greeks': {k: float(v) for k, v in summary['aggregate_greeks'].items()},
                    'positions': []
                }
            }
            
            for pos_data in summary['positions']:
                pos_dict = {
                    'symbol': pos_data['symbol'],
                    'strike': float(pos_data['strike']),
                    'expiration_days': float(pos_data['expiration_days']),
                    'option_type': pos_data['option_type'],
                    'quantity': pos_data['quantity'],
                    'market_price': float(pos_data['market_price']),
                    'theoretical_price': float(pos_data['theoretical_price']),
                    'market_value': float(pos_data['market_value']),
                    'theoretical_value': float(pos_data['theoretical_value']),
                    'unrealized_pnl': float(pos_data['unrealized_pnl']),
                    'greeks': {k: float(v) for k, v in pos_data['greeks'].items()}
                }
                if 'viability' in pos_data:
                    pos_dict['viability'] = pos_data['viability']
                result['portfolio']['positions'].append(pos_dict)
            
            return jsonify(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/api/portfolio/summary', methods=['GET'])
    @require_auth
    def api_portfolio_summary():
        """Get portfolio summary"""
        if not HAS_PORTFOLIO:
            return jsonify({'success': False, 'error': 'Portfolio modules not available'}), 503
        
        try:
            portfolio = get_user_portfolio()
            summary = portfolio.get_portfolio_summary()
            
            # Convert to JSON-serializable format
            result = {
                'success': True,
                'portfolio': {
                    'num_positions': summary['num_positions'],
                    'market_value': float(summary['market_value']),
                    'theoretical_value': float(summary['theoretical_value']),
                    'unrealized_pnl': float(summary['unrealized_pnl']),
                    'aggregate_greeks': {k: float(v) for k, v in summary['aggregate_greeks'].items()},
                    'positions': []
                }
            }
            
            for pos_data in summary['positions']:
                pos_dict = {
                    'symbol': pos_data['symbol'],
                    'strike': float(pos_data['strike']),
                    'expiration_days': float(pos_data['expiration_days']),
                    'option_type': pos_data['option_type'],
                    'quantity': pos_data['quantity'],
                    'market_price': float(pos_data['market_price']),
                    'theoretical_price': float(pos_data['theoretical_price']),
                    'market_value': float(pos_data['market_value']),
                    'theoretical_value': float(pos_data['theoretical_value']),
                    'unrealized_pnl': float(pos_data['unrealized_pnl']),
                    'greeks': {k: float(v) for k, v in pos_data['greeks'].items()}
                }
                # Include viability if available
                if 'viability' in pos_data:
                    pos_dict['viability'] = pos_data['viability']
                result['portfolio']['positions'].append(pos_dict)
            
            return jsonify(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/api/portfolio/greeks', methods=['GET'])
    @require_auth
    def api_portfolio_greeks():
        """Get aggregate Greeks from portfolio"""
        if not HAS_PORTFOLIO:
            return jsonify({'success': False, 'error': 'Portfolio modules not available'}), 503
        
        try:
            portfolio = get_user_portfolio()
            aggregate_greeks = portfolio.get_aggregate_greeks()
            return jsonify({
                'success': True,
                'aggregate_greeks': {k: float(v) for k, v in aggregate_greeks.items()}
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/api/portfolio/pnl_profile', methods=['POST'])
    @require_auth
    def api_portfolio_pnl_profile():
        """Calculate portfolio P&L profile"""
        if not HAS_PORTFOLIO:
            return jsonify({'success': False, 'error': 'Portfolio modules not available'}), 503
        
        try:
            data = request.json
            portfolio = get_user_portfolio()
            
            price_range = None
            if 'price_range' in data:
                pr = data['price_range']
                price_range = (float(pr['min']), float(pr['max']), int(pr.get('steps', 100)))
            
            spot_ref = float(data.get('spot_ref', 100))
            profile_data = portfolio.calculate_portfolio_pnl_profile(price_range, spot_ref)
            
            pnl_profile = profile_data.get('pnl_profile', [])
            payoff_profile = profile_data.get('payoff_profile', [])
            
            # Calcular breakeven (donde payoff = 0, usando el payoff profile que es más preciso)
            breakeven = spot_ref  # Default
            if payoff_profile and len(payoff_profile) > 1:
                # Buscar el punto donde payoff cruza cero
                for i in range(len(payoff_profile) - 1):
                    if payoff_profile[i]['payoff'] * payoff_profile[i+1]['payoff'] <= 0:
                        # Interpolación lineal para encontrar el punto exacto
                        x1, y1 = payoff_profile[i]['spot'], payoff_profile[i]['payoff']
                        x2, y2 = payoff_profile[i+1]['spot'], payoff_profile[i+1]['payoff']
                        if y2 != y1:
                            breakeven = x1 - y1 * (x2 - x1) / (y2 - y1)
                            break
                # Si no hay cruce, usar el spot donde payoff es mínimo (más cercano a cero)
                if breakeven == spot_ref:
                    min_abs_payoff_idx = min(range(len(payoff_profile)), key=lambda i: abs(payoff_profile[i]['payoff']))
                    breakeven = payoff_profile[min_abs_payoff_idx]['spot']
            
            current_pnl = float(pnl_profile[0]['pnl']) if pnl_profile else 0.0
            
            return jsonify({
                'success': True,
                'pnl_profile': pnl_profile,  # P&L actual (con time value)
                'payoff_profile': payoff_profile,  # Payoff al vencimiento (intrinsic only)
                'current_spot': spot_ref,
                'breakeven': float(breakeven),
                'current_pnl': current_pnl
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/api/portfolio/remove_position', methods=['POST'])
    @require_auth
    def api_remove_position():
        """Remove a position from portfolio"""
        if not HAS_PORTFOLIO:
            return jsonify({'success': False, 'error': 'Portfolio modules not available'}), 503
        
        try:
            data = request.json
            symbol = data.get('symbol')
            portfolio = get_user_portfolio()
            portfolio.remove_position(symbol)
            
            # Guardar portfolio
            if HAS_DATABASE and db:
                save_user_portfolio()
            
            return jsonify({'success': True, 'message': f'Removed {symbol}'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/api/portfolio/clear', methods=['POST'])
    @require_auth
    def api_clear_portfolio():
        """Clear all positions"""
        if not HAS_PORTFOLIO:
            return jsonify({'success': False, 'error': 'Portfolio modules not available'}), 503
        
        try:
            portfolio = get_user_portfolio()
            portfolio.clear()
            save_user_portfolio()  # Guardar después de limpiar
            return jsonify({'success': True, 'message': 'Portfolio cleared'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/portfolio')
    @require_auth
    def portfolio_page():
        """Portfolio page"""
        return render_template('portfolio.html')
    
    # =============================================================================
    # SUSCRIPCIONES
    # =============================================================================
    if HAS_SUBSCRIPTION:
        @app.route('/subscription')
        @require_auth
        def subscription_page():
            """Página de suscripciones"""
            return render_template('subscription.html')
        
        @app.route('/api/subscription/status', methods=['GET'])
        @require_auth
        def api_subscription_status():
            """Obtener estado de suscripción del usuario"""
            try:
                username = session.get('username', 'default')
                sub = subscription_manager.get_user_subscription(username)
                limits = subscription_manager.get_plan_limits(username)
                is_active = subscription_manager.check_subscription_active(username)
                
                return jsonify({
                    'success': True,
                    'subscription': sub,
                    'limits': limits,
                    'active': is_active
                })
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 400
        
        @app.route('/api/subscription/plans', methods=['GET'])
        @require_auth
        def api_subscription_plans():
            """Obtener planes disponibles"""
            try:
                plans = subscription_manager.get_available_plans()
                return jsonify({'success': True, 'plans': plans})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 400
        
        @app.route('/api/subscription/create_payment', methods=['POST'])
        @require_auth
        def api_create_payment():
            """Crear solicitud de pago en cripto"""
            try:
                if HAS_LOGGER:
                    app_logger.info("Creando solicitud de pago", context={'username': session.get('username')})
                
                # Validar inputs
                if HAS_SECURITY:
                    constraints = {
                        'plan': {'type': str, 'required': True, 'allowed_values': [p.value for p in SubscriptionPlan]},
                        'months': {'type': int, 'required': True, 'min': 1, 'max': 12},
                        'crypto_type': {'type': str, 'required': True, 'allowed_values': ['bitcoin', 'usdt', 'usdc', 'usdt_trc20', 'usdc_trc20']},
                        'email': {'type': str, 'required': True, 'max_length': 255},
                        'alias': {'type': str, 'required': True, 'max_length': 100}
                    }
                    data, error = security_manager.sanitize_input(request.json, constraints)
                    if error:
                        return jsonify({'success': False, 'error': error}), 400
                else:
                    data = request.json
                    plan_id = data.get('plan')
                    if plan_id not in [p.value for p in SubscriptionPlan]:
                        return jsonify({'success': False, 'error': 'Plan inválido'}), 400
                    data['plan'] = plan_id
                    
                    # Validar campos requeridos
                    if not data.get('email'):
                        return jsonify({'success': False, 'error': 'Email requerido'}), 400
                    if not data.get('alias'):
                        return jsonify({'success': False, 'error': 'ALYC/Alias requerido'}), 400
                    if not data.get('crypto_type'):
                        return jsonify({'success': False, 'error': 'Tipo de cripto requerido'}), 400
                
                # Validar formato de email
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, data.get('email', '')):
                    return jsonify({'success': False, 'error': 'Formato de email inválido'}), 400
                
                plan = SubscriptionPlan(data['plan'])
                username = session.get('username', 'default')
                months = data['months']
                crypto_type = data.get('crypto_type', 'usdt')
                user_email = data.get('email', '').strip().lower()
                user_alias = data.get('alias', '').strip()
                
                # Crear solicitud de pago con datos del usuario
                payment_info = subscription_manager.create_payment_request(
                    username, plan, months, crypto_type,
                    user_email=user_email,
                    user_alias=user_alias
                )
                
                if HAS_LOGGER:
                    app_logger.info("Pago creado", context={'payment_id': payment_info['payment_id'], 'username': username})
                
                return jsonify({
                    'success': True,
                    'payment': payment_info
                })
            except Exception as e:
                if HAS_LOGGER:
                    app_logger.error("Error creando pago", error=e, context={'username': session.get('username')})
                return jsonify({'success': False, 'error': str(e)}), 400
        
        @app.route('/api/subscription/verify_payment', methods=['POST'])
        @require_auth
        def api_verify_payment():
            """Verificar pago y autorizar suscripción"""
            try:
                if HAS_SECURITY:
                    constraints = {
                        'payment_id': {'type': str, 'required': True},
                        'tx_hash': {'type': str, 'required': True}
                    }
                    data, error = security_manager.sanitize_input(request.json, constraints)
                    if error:
                        return jsonify({'success': False, 'error': error}), 400
                else:
                    data = request.json
                    if not data.get('payment_id') or not data.get('tx_hash'):
                        return jsonify({'success': False, 'error': 'payment_id y tx_hash requeridos'}), 400
                
                payment_id = data['payment_id']
                tx_hash = data['tx_hash']
                username = session.get('username', 'default')
                
                # Verificar que el pago pertenece al usuario
                payment_status = subscription_manager.check_payment_status(payment_id)
                if payment_status.get('status') == 'not_found':
                    return jsonify({'success': False, 'error': 'Pago no encontrado'}), 404
                
                # Verificar ownership del pago (si está en DB)
                if HAS_DATABASE and db:
                    payment = db.get_pending_payment(payment_id)
                    if payment and payment.get('username') != username:
                        return jsonify({'success': False, 'error': 'No tienes permiso para verificar este pago'}), 403
                
                # Verificar pago
                verified, message = subscription_manager.verify_payment(payment_id, tx_hash)
                
                if verified:
                    if HAS_LOGGER:
                        app_logger.info("Pago verificado y suscripción activada", 
                                       context={'payment_id': payment_id, 'tx_hash': tx_hash, 'username': username})
                    
                    # Obtener información actualizada del plan para incluir en la respuesta
                    limits = subscription_manager.get_plan_limits(username)
                    sub = subscription_manager.get_user_subscription(username)
                    
                    return jsonify({
                        'success': True,
                        'message': message,
                        'subscription': {
                            'plan': sub['plan'],
                            'active': subscription_manager.check_subscription_active(username),
                            'limits': limits
                        }
                    })
                else:
                    if HAS_LOGGER:
                        app_logger.warning("Verificación de pago fallida", 
                                          context={'payment_id': payment_id, 'message': message})
                    return jsonify({
                        'success': False,
                        'error': message
                    }), 400
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                if HAS_LOGGER:
                    app_logger.error("Error verificando pago", error=e, context={'traceback': error_trace})
                else:
                    print(f"[ERROR] Error verificando pago: {e}")
                    print(error_trace)
                return jsonify({
                    'success': False, 
                    'error': str(e) if str(e) else 'Error desconocido al verificar el pago'
                }), 500
        
        @app.route('/api/subscription/payment_status/<payment_id>', methods=['GET'])
        @require_auth
        def api_payment_status(payment_id):
            """Verificar estado de un pago"""
            try:
                username = session.get('username', 'default')
                status = subscription_manager.check_payment_status(payment_id)
                
                # Verificar ownership
                if status.get('status') != 'not_found' and HAS_DATABASE and db:
                    payment = db.get_pending_payment(payment_id)
                    if payment and payment.get('username') != username:
                        return jsonify({'success': False, 'error': 'Acceso denegado'}), 403
                
                return jsonify({
                    'success': True,
                    'status': status
                })
            except Exception as e:
                if HAS_LOGGER:
                    app_logger.error("Error obteniendo estado de pago", error=e)
                return jsonify({'success': False, 'error': str(e)}), 400
        
        @app.route('/api/subscription/pending_payments', methods=['GET'])
        @require_auth
        def api_pending_payments():
            """Obtener pagos pendientes del usuario"""
            try:
                username = session.get('username', 'default')
                if HAS_DATABASE and db:
                    payments = db.get_all_pending_payments(username)
                    # Filtrar solo pendientes y convertir a formato JSON
                    pending = [
                        {
                            'payment_id': p['payment_id'],
                            'plan': p['plan'],
                            'months': p['months'],
                            'amount_crypto': p['amount_crypto'],
                            'crypto_type': p['crypto_type'],
                            'amount_usd': p['amount_usd'],
                            'status': p['status'],
                            'created_at': p['created_at'],
                            'expires_at': p['expires_at']
                        }
                        for p in payments if p['status'] == 'pending'
                    ]
                    return jsonify({'success': True, 'payments': pending})
                else:
                    # Fallback a memoria (no implementado completamente)
                    return jsonify({'success': True, 'payments': []})
            except Exception as e:
                if HAS_LOGGER:
                    app_logger.error("Error obteniendo pagos pendientes", error=e)
                return jsonify({'success': False, 'error': str(e)}), 400
        
        @app.route('/api/subscription/payment_history', methods=['GET'])
        @require_auth
        def api_payment_history():
            """Obtener historial de pagos del usuario"""
            try:
                username = session.get('username', 'default')
                if HAS_DATABASE and db:
                    history = db.get_payment_history(username)
                    return jsonify({'success': True, 'history': history})
                else:
                    return jsonify({'success': True, 'history': []})
            except Exception as e:
                if HAS_LOGGER:
                    app_logger.error("Error obteniendo historial de pagos", error=e)
                return jsonify({'success': False, 'error': str(e)}), 400
        
        @app.route('/api/subscription/upgrade', methods=['POST'])
        @require_auth
        def api_subscription_upgrade():
            """DEPRECATED: Usar /api/subscription/create_payment en su lugar"""
            return jsonify({
                'success': False,
                'error': 'Endpoint deprecado. Usa /api/subscription/create_payment para pagos en cripto'
            }), 400

    # =============================================================================
    # CHATBOT
    # =============================================================================
    if HAS_CHATBOT:
        @app.route('/api/chat/status', methods=['GET'])
        @require_auth
        def api_chat_status():
            """Endpoint de diagnóstico del chatbot"""
            try:
                if chatbot is None:
                    return jsonify({
                        'success': False,
                        'error': 'Chatbot no está disponible.',
                        'status': {
                            'available': False,
                            'error': 'El módulo chatbot no se pudo cargar'
                        }
                    }), 503
                
                status = {
                    'ollama_available': getattr(chatbot, 'ollama_available', False),
                    'client_type': getattr(chatbot, 'client_type', 'unknown'),
                    'model': getattr(chatbot, 'model', 'unknown'),
                    'ollama_url': getattr(chatbot, 'ollama_url', 'http://localhost:11434'),
                    'use_ollama': getattr(chatbot, 'use_ollama', False),
                    'has_openai_key': bool(getattr(chatbot, 'api_key', None))
                }
                
                # Verificar Ollama ahora
                if chatbot is not None and hasattr(chatbot, '_check_ollama_available'):
                    status['ollama_check_now'] = chatbot._check_ollama_available()
                    chatbot.ollama_available = status['ollama_check_now']
                
                return jsonify({'success': True, 'status': status})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 400
        
        @app.route('/api/chat', methods=['POST'])
        @require_auth
        def api_chat():
            """Endpoint para el chatbot"""
            # Verificar que el chatbot esté disponible
            if not HAS_CHATBOT or chatbot is None:
                return jsonify({
                    'success': False,
                    'error': 'Chatbot no está disponible. El módulo no se pudo cargar.',
                    'response': '⚠️ Chatbot no disponible. Verifica los logs del servidor.'
                }), 503
            
            try:
                data = request.json
                user_message = data.get('message', '').strip()
                
                if not user_message:
                    return jsonify({'success': False, 'error': 'Mensaje vacío'}), 400
                
                # Obtener contexto del portfolio si está disponible
                portfolio_context = None
                if HAS_PORTFOLIO and chatbot is not None:
                    try:
                        portfolio = get_user_portfolio()
                        summary = portfolio.get_portfolio_summary()
                        # Usar .get() para evitar KeyError si alguna clave falta
                        portfolio_context = chatbot.get_portfolio_context({
                            'num_positions': summary.get('num_positions', 0),
                            'market_value': summary.get('market_value', 0.0),
                            'theoretical_value': summary.get('theoretical_value', 0.0),
                            'unrealized_pnl': summary.get('unrealized_pnl', 0.0),
                            'aggregate_greeks': summary.get('aggregate_greeks', {})
                        })
                    except Exception as e:
                        print(f"[DEBUG] Error obteniendo contexto del portfolio: {e}")
                        pass  # Si falla, continuar sin contexto
                
                # Obtener historial de conversación (opcional)
                conversation_history = data.get('history', [])
                
                # CRÍTICO: Forzar verificación de Ollama ANTES de generar respuesta
                # Esto asegura que detectemos si Ollama se inició después de Flask
                if chatbot is not None and hasattr(chatbot, '_check_ollama_available') and hasattr(chatbot, 'use_ollama') and chatbot.use_ollama:
                    try:
                        print(f"[DEBUG] Verificando Ollama en {chatbot.ollama_url}...")
                        current_available = chatbot._check_ollama_available()
                        print(f"[DEBUG] Ollama disponible: {current_available}")
                        
                        chatbot.ollama_available = current_available
                        
                        # Si ahora está disponible, actualizar client_type
                        if current_available and chatbot.use_ollama:
                            chatbot.client_type = 'ollama'
                            print(f"[DEBUG] Usando Ollama con modelo: {chatbot.model}")
                            if HAS_LOGGER:
                                app_logger.info("Ollama verificado y disponible", context={
                                    'model': chatbot.model,
                                    'url': chatbot.ollama_url
                                })
                        else:
                            current_client_type = getattr(chatbot, 'client_type', 'unknown')
                            print(f"[DEBUG] Ollama no disponible. Client type: {current_client_type}")
                            if HAS_LOGGER:
                                app_logger.warning("Ollama no disponible", context={
                                    'url': getattr(chatbot, 'ollama_url', 'unknown'),
                                    'model': getattr(chatbot, 'model', 'unknown'),
                                    'use_ollama': getattr(chatbot, 'use_ollama', False)
                                })
                    except Exception as e:
                        print(f"[DEBUG] Error verificando Ollama: {e}")
                        if HAS_LOGGER:
                            app_logger.warning("Error verificando Ollama", context={'error': str(e)})
                        # Continuar de todas formas, el generate_response manejará el error
                
                # Generar respuesta
                # Verificar nuevamente que chatbot no sea None antes de usarlo
                if chatbot is None:
                    return jsonify({
                        'success': False,
                        'error': 'Chatbot no está disponible.',
                        'response': '⚠️ Chatbot no disponible. Verifica los logs del servidor.'
                    }), 503
                
                ollama_available = getattr(chatbot, 'ollama_available', False)
                client_type = getattr(chatbot, 'client_type', 'unknown')
                print(f"[DEBUG] Generando respuesta. Ollama available: {ollama_available}, Client type: {client_type}")
                if HAS_LOGGER:
                    app_logger.info("Generando respuesta del chatbot", context={
                        'username': session.get('username'),
                        'message_length': len(user_message),
                        'ollama_available': ollama_available,
                        'client_type': client_type
                    })
                
                response = chatbot.generate_response(
                    user_message, 
                    portfolio_context, 
                    conversation_history
                )
                
                # Validar que response no sea None
                if response is None:
                    response = "⚠️ El chatbot no devolvió respuesta"
                
                print(f"[DEBUG] Response recibida: {response[:100]}...")
                
                # Limpiar respuesta de caracteres problemáticos si es necesario
                if isinstance(response, str):
                    # Asegurar que la respuesta sea válida UTF-8
                    try:
                        response = response.encode('utf-8', errors='replace').decode('utf-8')
                    except:
                        pass
                
                if HAS_LOGGER:
                    app_logger.info("Respuesta generada", context={
                        'username': session.get('username'),
                        'response_length': len(response) if response else 0,
                        'is_error': response.startswith('⚠️') if response else False,
                        'client_type': getattr(chatbot, 'client_type', 'unknown')
                    })
                
                # Verificar si la respuesta es un error
                is_error = response.startswith('⚠️') if response else False
                print(f"[DEBUG] Is error: {is_error}, Success: {not is_error}")
                
                return jsonify({
                    'success': not is_error,  # Si es error, success=False
                    'response': response,
                    'is_error': is_error
                })
            except Exception as e:
                error_msg = str(e)
                import traceback
                error_trace = traceback.format_exc()
                print(f"[ERROR] Chat endpoint exception: {error_msg}")
                print(f"[ERROR] Full traceback:")
                print(error_trace)
                
                if HAS_LOGGER:
                    try:
                        app_logger.error("Error en endpoint de chat", error=e, context={
                            'username': session.get('username', 'unknown'),
                            'message_length': len(user_message) if 'user_message' in locals() else 0,
                            'error_type': type(e).__name__
                        })
                    except:
                        pass  # Si el logger falla, continuar sin él
                
                # Devolver error más descriptivo (500 = error interno del servidor)
                return jsonify({
                    'success': False, 
                    'error': f'Error generando respuesta: {error_msg}',
                    'response': f'⚠️ Error: {error_msg}',
                    'error_type': type(e).__name__
                }), 500

# Endpoints para análisis estadístico avanzado
if HAS_STAT_ANALYSIS:
    @app.route('/api/expected_move', methods=['POST'])
    @require_auth
    def api_expected_move():
        """Calcular Expected Move"""
        try:
            data = request.json
            spot = float(data.get('spot'))
            iv = float(data.get('implied_vol', 20)) / 100
            dte = float(data.get('days_to_expiration', 30))
            
            expected_move = calcular_expected_move(spot, iv, dte)
            
            return jsonify({
                'success': True,
                'expected_move': expected_move
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
# Endpoint de distribución de probabilidad (implementación independiente)
    @app.route('/api/probability_distribution', methods=['POST'])
    @require_auth
    def api_probability_distribution():
        """Calcular distribución de probabilidad lognormal con PDF de opción y probabilidades"""
        try:
            data = request.json
            spot = float(data.get('spot'))
            iv = float(data.get('implied_vol', 20)) / 100
            dte = float(data.get('days_to_expiration', 30))
            risk_free = float(data.get('risk_free_rate', 0)) / 100
            strike = float(data.get('strike', spot))  # Si no se proporciona, usar spot (ATM)
            option_type = data.get('option_type', 'call')  # 'call' o 'put'
            
            # Implementación directa sin depender de HAS_STAT_ANALYSIS
            import numpy as np
            from scipy import stats
            
            # Calcular distribución lognormal del subyacente
            # Parámetros de la distribución lognormal
            # Si S sigue lognormal: ln(S) ~ N(μ, σ²)
            # μ = ln(S0) + (r - 0.5*σ²)*T
            # σ = σ_implied * sqrt(T)
            
            T = dte / 365.0
            sigma = iv * np.sqrt(T)
            mu = np.log(spot) + (risk_free - 0.5 * iv**2) * T
            
            # Rango de precios (3 desviaciones estándar a cada lado)
            price_range = np.linspace(spot * 0.3, spot * 2.0, 500)
            
            # PDF lognormal del subyacente
            pdf_underlying = stats.lognorm.pdf(price_range, s=sigma, scale=np.exp(mu))
            
            # CDF del subyacente
            cdf_underlying = stats.lognorm.cdf(price_range, s=sigma, scale=np.exp(mu))
            
            # Estadísticas del subyacente
            mode_price = np.exp(mu - sigma**2)
            expected_price = np.exp(mu + 0.5 * sigma**2)
            median_price = np.exp(mu)
            std_price = np.sqrt((np.exp(sigma**2) - 1) * np.exp(2*mu + sigma**2))
            
            # Calcular PDF de la opción
            # La PDF de la opción se calcula transformando la PDF del subyacente
            # Para cada precio spot S, calculamos el precio de la opción C(S) y su PDF
            option_pdf = []
            option_prices_range = []
            
            try:
                from opciones_comparador import black_scholes_advanced
                
                # Calcular precios de opción y sus derivadas (delta) para transformar la PDF
                option_prices_list = []
                deltas = []
                
                for i, s in enumerate(price_range):
                    try:
                        # Calcular precio teórico de la opción
                        opt_price = black_scholes_advanced(
                            'prima', s, strike, T, risk_free, 0.0,
                            iv, option_type,
                            'accion', ''
                        )
                        option_prices_list.append(float(opt_price))
                        
                        # Calcular delta (derivada del precio de la opción respecto al spot)
                        # Delta = dC/dS, necesario para transformar la PDF
                        # Usamos diferencia finita para aproximar delta
                        if i > 0:
                            ds = price_range[i] - price_range[i-1]
                            if ds > 0:
                                prev_price = black_scholes_advanced(
                                    'prima', price_range[i-1], strike, T, risk_free, 0.0,
                                    iv, option_type, 'accion', ''
                                )
                                delta = (float(opt_price) - float(prev_price)) / ds
                                deltas.append(abs(delta) if delta != 0 else 1.0)
                            else:
                                deltas.append(1.0)
                        else:
                            deltas.append(1.0)
                    except:
                        option_prices_list.append(0.0)
                        deltas.append(1.0)
                
                # Transformar PDF: f_option(C) = f_underlying(S) / |dC/dS|
                # donde C = precio de opción y S = precio spot
                if len(option_prices_list) == len(price_range) and len(deltas) == len(price_range):
                    option_pdf = (pdf_underlying / np.array(deltas)).tolist()
                    option_prices_range = option_prices_list
                else:
                    # Fallback: usar PDF del subyacente directamente
                    option_pdf = pdf_underlying.tolist()
                    option_prices_range = price_range.tolist()
                    
            except ImportError:
                # Si no está disponible black_scholes_advanced, usar PDF del subyacente
                option_pdf = pdf_underlying.tolist()
                option_prices_range = price_range.tolist()
            
            # Calcular probabilidades bajo la curva
            # Probabilidad de que el precio esté en diferentes rangos
            prob_itm_call = 1 - stats.lognorm.cdf(strike, s=sigma, scale=np.exp(mu))
            prob_itm_put = stats.lognorm.cdf(strike, s=sigma, scale=np.exp(mu))
            
            # Probabilidades en rangos específicos
            prob_below_spot = stats.lognorm.cdf(spot, s=sigma, scale=np.exp(mu))
            prob_above_spot = 1 - prob_below_spot
            
            # Probabilidad en ±1, ±2 desviaciones estándar
            prob_1std_below = stats.lognorm.cdf(expected_price - std_price, s=sigma, scale=np.exp(mu))
            prob_1std_above = 1 - stats.lognorm.cdf(expected_price + std_price, s=sigma, scale=np.exp(mu))
            prob_1std_range = 1 - prob_1std_below - prob_1std_above
            
            prob_2std_below = stats.lognorm.cdf(expected_price - 2*std_price, s=sigma, scale=np.exp(mu))
            prob_2std_above = 1 - stats.lognorm.cdf(expected_price + 2*std_price, s=sigma, scale=np.exp(mu))
            prob_2std_range = 1 - prob_2std_below - prob_2std_above
            
            # Distribución del subyacente
            underlying_dist = {
                'prices': price_range.tolist(),
                'pdf': pdf_underlying.tolist(),
                'cdf': cdf_underlying.tolist(),
                'mode_price': float(mode_price),
                'expected_price': float(expected_price),
                'median_price': float(median_price),
                'std_price': float(std_price)
            }
            
            # Distribución de la opción
            option_dist = {
                'prices': option_prices_range if option_prices_range else price_range.tolist(),
                'pdf': option_pdf,
                'strike': float(strike),
                'option_type': option_type
            }
            
            # Probabilidades
            probabilities = {
                'call_itm': float(prob_itm_call),
                'put_itm': float(prob_itm_put),
                'below_spot': float(prob_below_spot),
                'above_spot': float(prob_above_spot),
                'within_1std': float(prob_1std_range),
                'within_2std': float(prob_2std_range),
                'below_1std': float(prob_1std_below),
                'above_1std': float(prob_1std_above),
                'below_2std': float(prob_2std_below),
                'above_2std': float(prob_2std_above)
            }
            
            return jsonify({
                'success': True,
                'distribution': underlying_dist,  # Mantener compatibilidad
                'underlying': underlying_dist,
                'option': option_dist,
                'probabilities': probabilities
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 400
    
# Endpoints para carga de datos (no dependen de HAS_STAT_ANALYSIS)
@app.route('/api/download_price_data', methods=['POST'])
@require_auth
def api_download_price_data():
    """Descargar datos históricos de Yahoo Finance"""
    try:
        data = request.json
        ticker = data.get('ticker', '').upper()
        period = data.get('period', '1y')  # 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        interval = data.get('interval', '1d')  # 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
        
        if not ticker:
            return jsonify({'success': False, 'error': 'Ticker requerido'}), 400
        
        import yfinance as yf
        import pandas as pd
        import numpy as np
        
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, interval=interval)
        
        if hist.empty:
            return jsonify({'success': False, 'error': f'No se encontraron datos para {ticker}'}), 400
        
        # Obtener datos OHLC para velas
        prices = hist['Close'].values
        opens = hist['Open'].values
        highs = hist['High'].values
        lows = hist['Low'].values
        volumes = hist['Volume'].values if 'Volume' in hist.columns else None
        
        # Calcular retornos logarítmicos
        log_returns = np.diff(np.log(prices))
        
        # Estadísticas
        returns = log_returns
        
        # Preparar datos OHLC para gráficos de velas (formato esperado por el frontend)
        ohlc_data = []
        for idx in range(len(hist)):
            ohlc_data.append({
                'open': float(opens[idx]),
                'high': float(highs[idx]),
                'low': float(lows[idx]),
                'close': float(prices[idx]),
                'volume': float(volumes[idx]) if volumes is not None and idx < len(volumes) else 0
            })
        
        # Formatear fechas con hora si el intervalo es menor a 1 día
        date_format = '%Y-%m-%d %H:%M:%S' if interval in ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h'] else '%Y-%m-%d'
        
        result = {
            'success': True,
            'ticker': ticker,
            'dates': hist.index.strftime(date_format).tolist(),
            'prices': prices.tolist(),
            'opens': opens.tolist(),
            'highs': highs.tolist(),
            'lows': lows.tolist(),
            'volumes': volumes.tolist() if volumes is not None else None,
            'ohlc': ohlc_data,  # Datos OHLC en formato para gráficos de velas
            'returns': returns.tolist(),
            'period': period,
            'interval': interval,
            'statistics': {
                'mean_return': float(np.mean(returns)),
                'std_return': float(np.std(returns)),
                'annualized_vol': float(np.std(returns) * np.sqrt(252)),
                'current_price': float(prices[-1]),
                'min_price': float(np.min(prices)),
                'max_price': float(np.max(prices)),
                'num_points': len(prices)
            }
        }
        
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/api/realtime_price_data', methods=['POST'])
    @require_auth
    def api_realtime_price_data():
        """Obtener datos actualizados en tiempo real desde Yahoo Finance"""
        try:
            data = request.json
            ticker = data.get('ticker', '').upper()
            period = data.get('period', '1d')  # Para tiempo real, usar periodos cortos
            interval = data.get('interval', '1m')  # Intervalo de 1 minuto para datos más recientes
            
            if not ticker:
                return jsonify({'success': False, 'error': 'Ticker requerido'}), 400
            
            import yfinance as yf
            import pandas as pd
            import numpy as np
            from datetime import datetime, timedelta
            
            stock = yf.Ticker(ticker)
            
            # Obtener datos más recientes (últimas horas/días según el periodo)
            hist = stock.history(period=period, interval=interval)
            
            if hist.empty:
                return jsonify({'success': False, 'error': f'No se encontraron datos para {ticker}'}), 400
            
            # Obtener información en tiempo real
            try:
                info = stock.info
                current_price = info.get('regularMarketPrice') or info.get('currentPrice') or float(hist['Close'].iloc[-1])
                previous_close = info.get('previousClose') or (float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price)
            except:
                current_price = float(hist['Close'].iloc[-1])
                previous_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
            
            # Calcular cambio
            change = current_price - previous_close
            change_percent = (change / previous_close * 100) if previous_close > 0 else 0
            
            # Obtener datos OHLC para velas
            prices = hist['Close'].values
            opens = hist['Open'].values
            highs = hist['High'].values
            lows = hist['Low'].values
            volumes = hist['Volume'].values if 'Volume' in hist.columns else None
            
            # Calcular retornos logarítmicos
            log_returns = np.diff(np.log(prices)) if len(prices) > 1 else np.array([0])
            returns = log_returns
            
            # Preparar datos OHLC para gráficos de velas
            ohlc_data = []
            for idx in range(len(hist)):
                ohlc_data.append({
                    'open': float(opens[idx]),
                    'high': float(highs[idx]),
                    'low': float(lows[idx]),
                    'close': float(prices[idx]),
                    'volume': float(volumes[idx]) if volumes is not None and idx < len(volumes) else 0
                })
            
            # Formatear fechas con hora si el intervalo es menor a 1 día
            date_format = '%Y-%m-%d %H:%M:%S' if interval in ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h'] else '%Y-%m-%d'
            
            result = {
                'success': True,
                'ticker': ticker,
                'dates': hist.index.strftime(date_format).tolist(),
                'prices': prices.tolist(),
                'opens': opens.tolist(),
                'highs': highs.tolist(),
                'lows': lows.tolist(),
                'volumes': volumes.tolist() if volumes is not None else None,
                'ohlc': ohlc_data,
                'returns': returns.tolist(),
                'realtime': {
                    'current_price': float(current_price),
                    'previous_close': float(previous_close),
                    'change': float(change),
                    'change_percent': float(change_percent),
                    'timestamp': datetime.now().isoformat()
                },
                'statistics': {
                    'mean_return': float(np.mean(returns)) if len(returns) > 0 else 0,
                    'std_return': float(np.std(returns)) if len(returns) > 0 else 0,
                    'annualized_vol': float(np.std(returns) * np.sqrt(252)) if len(returns) > 0 else 0,
                    'current_price': float(current_price),
                    'min_price': float(np.min(prices)),
                    'max_price': float(np.max(prices)),
                    'num_points': len(prices)
                }
            }
            
            return jsonify(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/upload_excel_data', methods=['POST'])
@require_auth
def api_upload_excel_data():
    """Subir y procesar datos de Excel con validación robusta"""
    try:
        app.logger.info("Iniciando procesamiento de archivo Excel/CSV")
        
        if 'file' not in request.files:
            app.logger.warning("No se recibió archivo en la petición")
            return jsonify({'success': False, 'error': 'No se recibió archivo'}), 400
        
        file = request.files['file']
        if file.filename == '':
            app.logger.warning("Nombre de archivo vacío")
            return jsonify({'success': False, 'error': 'Archivo vacío'}), 400
        
        app.logger.info(f"Procesando archivo: {file.filename}")
        
        import pandas as pd
        import numpy as np
        import io
        
        # Leer Excel o CSV con manejo de errores
        try:
            if file.filename.endswith('.csv'):
                app.logger.debug("Leyendo archivo CSV")
                df = pd.read_csv(file, na_values=['#N/A', '#NA', '#NULL', 'N/A', 'NA', 'NULL', 'null', '', ' ', '-', 'NaN'])
            else:
                app.logger.debug("Leyendo archivo Excel")
                df = pd.read_excel(file, na_values=['#N/A', '#NA', '#NULL', 'N/A', 'NA', 'NULL', 'null', '', ' ', '-', 'NaN'])
        except Exception as read_error:
            app.logger.error(f"Error leyendo archivo: {read_error}")
            import traceback
            app.logger.error(traceback.format_exc())
            return jsonify({
                'success': False, 
                'error': f'Error al leer archivo: {str(read_error)}. Verifique que el formato sea válido.'
            }), 400
        
        if df.empty:
            app.logger.warning("DataFrame vacío después de leer archivo")
            return jsonify({'success': False, 'error': 'El archivo está vacío o no contiene datos válidos'}), 400
        
        app.logger.debug(f"DataFrame cargado: {len(df)} filas, {len(df.columns)} columnas")
        
        # Buscar columna de precios (Close, Precio, Price, etc.)
        price_col = None
        for col in df.columns:
            if any(word in col.lower() for word in ['close', 'precio', 'price', 'c']):
                price_col = col
                app.logger.debug(f"Columna de precio encontrada: {col}")
                break
        
        if price_col is None:
            # Usar última columna numérica
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                price_col = numeric_cols[-1]
                app.logger.debug(f"Usando última columna numérica como precio: {price_col}")
            else:
                app.logger.error("No se encontró ninguna columna numérica válida")
                return jsonify({'success': False, 'error': 'No se encontró columna de precios válida'}), 400
        
        # Validar y limpiar datos de precios
        app.logger.debug(f"Procesando columna de precios: {price_col}")
        price_series = df[price_col]
        
        # Reemplazar valores nulos y errores
        price_series = price_series.replace([np.inf, -np.inf], np.nan)
        
        # Eliminar nulos, valores <= 0 y NaN
        prices = price_series.dropna()
        prices = prices[prices > 0]  # Solo precios positivos
        
        if len(prices) < 2:
            app.logger.error(f"Datos insuficientes: solo {len(prices)} precios válidos")
            return jsonify({
                'success': False, 
                'error': f'Datos insuficientes: se encontraron {len(prices)} precios válidos. Se requieren al menos 2 precios válidos (sin #N/A, vacíos o ceros).'
            }), 400
        
        app.logger.info(f"Procesando {len(prices)} precios válidos")
        
        # Convertir a numpy array y validar tipos
        try:
            prices = prices.astype(float).values
        except (ValueError, TypeError) as type_error:
            app.logger.error(f"Error convirtiendo precios a float: {type_error}")
            return jsonify({
                'success': False, 
                'error': f'Error al convertir precios a números: {str(type_error)}. Verifique que los valores sean numéricos.'
            }), 400
        
        # Validar que no haya valores inválidos
        if np.any(np.isnan(prices)) or np.any(np.isinf(prices)) or np.any(prices <= 0):
            # Filtrar valores inválidos
            valid_mask = ~(np.isnan(prices) | np.isinf(prices) | (prices <= 0))
            prices = prices[valid_mask]
            
            if len(prices) < 2:
                app.logger.error("Después de filtrar valores inválidos, quedan menos de 2 precios")
                return jsonify({
                    'success': False, 
                    'error': 'Después de filtrar valores inválidos (#N/A, vacíos, ceros, infinitos), quedan menos de 2 precios válidos.'
                }), 400
        
        app.logger.debug(f"Precios validados: min={np.min(prices):.2f}, max={np.max(prices):.2f}, count={len(prices)}")
        
        # Calcular retornos logarítmicos con validación
        try:
            # Validar que todos los precios sean positivos antes de calcular log
            if np.any(prices <= 0):
                app.logger.error("Se encontraron precios no positivos antes de calcular retornos")
                return jsonify({
                    'success': False, 
                    'error': 'Error: se encontraron precios no positivos. Verifique los datos.'
                }), 400
            
            returns = np.diff(np.log(prices))
            
            # Validar retornos (debe haber al menos 1 retorno)
            if len(returns) == 0:
                app.logger.error("No se pudieron calcular retornos")
                return jsonify({
                    'success': False, 
                    'error': 'Error al calcular retornos: datos insuficientes.'
                }), 400
            
            # Filtrar retornos inválidos
            returns = returns[~(np.isnan(returns) | np.isinf(returns))]
            
            if len(returns) == 0:
                app.logger.error("Todos los retornos calculados son inválidos")
                return jsonify({
                    'success': False, 
                    'error': 'Error: todos los retornos calculados son inválidos.'
                }), 400
            
        except Exception as calc_error:
            app.logger.error(f"Error calculando retornos: {calc_error}")
            import traceback
            app.logger.error(traceback.format_exc())
            return jsonify({
                'success': False, 
                'error': f'Error al calcular retornos: {str(calc_error)}'
            }), 400
        
        app.logger.debug(f"Retornos calculados: count={len(returns)}, mean={np.mean(returns):.6f}, std={np.std(returns):.6f}")
        
        # Calcular estadísticas con protección contra divisiones por cero
        try:
            mean_return = float(np.mean(returns)) if len(returns) > 0 else 0.0
            std_return = float(np.std(returns)) if len(returns) > 0 else 0.0
            
            # Volatilidad anualizada: proteger contra std_return = 0
            if std_return > 0:
                annualized_vol = float(std_return * np.sqrt(252))
            else:
                app.logger.warning("Desviación estándar de retornos es cero, usando volatilidad cero")
                annualized_vol = 0.0
            
            current_price = float(prices[-1]) if len(prices) > 0 else 0.0
            min_price = float(np.min(prices)) if len(prices) > 0 else 0.0
            max_price = float(np.max(prices)) if len(prices) > 0 else 0.0
            
        except Exception as stats_error:
            app.logger.error(f"Error calculando estadísticas: {stats_error}")
            import traceback
            app.logger.error(traceback.format_exc())
            return jsonify({
                'success': False, 
                'error': f'Error al calcular estadísticas: {str(stats_error)}'
            }), 500
        
        result = {
            'success': True,
            'prices': [float(p) for p in prices.tolist()],
            'returns': [float(r) for r in returns.tolist()],
            'statistics': {
                'mean_return': mean_return,
                'std_return': std_return,
                'annualized_vol': annualized_vol,
                'current_price': current_price,
                'min_price': min_price,
                'max_price': max_price,
                'num_points': len(prices)
            }
        }
        
        app.logger.info(f"Procesamiento exitoso: {len(prices)} precios, volatilidad anualizada: {annualized_vol:.2%}")
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error inesperado en api_upload_excel_data: {e}")
        import traceback
        error_trace = traceback.format_exc()
        app.logger.error(error_trace)
        return jsonify({
            'success': False, 
            'error': f'Error procesando archivo: {str(e)}',
            'details': 'Revise los logs del servidor para más información.'
        }), 500

@app.route('/api/probability_distribution_from_data', methods=['POST'])
@require_auth
def api_probability_distribution_from_data():
    """Calcular distribución desde datos históricos (acción y opción) con validación robusta"""
    try:
        app.logger.info("Iniciando cálculo de distribución de probabilidad desde datos históricos")
        
        data = request.json
        if not data:
            app.logger.warning("No se recibieron datos en la petición")
            return jsonify({'success': False, 'error': 'No se recibieron datos'}), 400
        
        # Validar y obtener parámetros con valores por defecto seguros
        try:
            spot = float(data.get('spot', 0))
            strike = float(data.get('strike', 0))
            dte = float(data.get('days_to_expiration', 30))
            risk_free = float(data.get('risk_free_rate', 0)) / 100
        except (ValueError, TypeError) as param_error:
            app.logger.error(f"Error procesando parámetros: {param_error}")
            return jsonify({
                'success': False, 
                'error': f'Error en parámetros: {str(param_error)}. Verifique que spot, strike y days_to_expiration sean números válidos.'
            }), 400
        
        # Validar parámetros críticos
        if spot <= 0:
            app.logger.error(f"Spot price inválido: {spot}")
            return jsonify({'success': False, 'error': 'Spot price debe ser mayor que cero'}), 400
        
        if strike <= 0:
            app.logger.error(f"Strike price inválido: {strike}")
            return jsonify({'success': False, 'error': 'Strike price debe ser mayor que cero'}), 400
        
        if dte <= 0:
            app.logger.error(f"Days to expiration inválido: {dte}")
            return jsonify({'success': False, 'error': 'Days to expiration debe ser mayor que cero'}), 400
        
        if dte > 3650:  # Más de 10 años parece poco razonable
            app.logger.warning(f"Days to expiration muy alto: {dte}, limitando a 3650")
            dte = 3650
        
        app.logger.debug(f"Parámetros validados: spot={spot}, strike={strike}, dte={dte}, risk_free={risk_free}")
        
        # Datos históricos del activo
        historical_returns = data.get('historical_returns', [])
        historical_prices = data.get('historical_prices', [])
        
        if not historical_returns and not historical_prices:
            app.logger.warning("No se proporcionaron datos históricos, usando volatilidad por defecto")
            hist_vol = 0.2  # Default 20%
        else:
            import numpy as np
            from scipy import stats
            
            # Calcular volatilidad histórica si tenemos retornos logarítmicos
            try:
                if historical_returns:
                    app.logger.debug(f"Calculando volatilidad desde {len(historical_returns)} retornos")
                    returns = np.array(historical_returns)
                    
                    # Filtrar valores inválidos (NaN, infinitos)
                    returns = returns[~(np.isnan(returns) | np.isinf(returns))]
                    
                    if len(returns) < 2:
                        app.logger.warning(f"Retornos insuficientes ({len(returns)}), usando volatilidad por defecto")
                        hist_vol = 0.2
                    else:
                        # Si los retornos vienen como simples, convertirlos a log
                        # (asumimos que si el valor es > 1, son retornos simples)
                        if np.any(np.abs(returns) > 1):
                            # Son retornos simples, convertirlos a log: log(1+r)
                            returns = np.log1p(returns)
                        
                        std_ret = np.std(returns)
                        if std_ret > 0:
                            hist_vol = float(std_ret * np.sqrt(252))  # Anualizada
                            # Limitar volatilidad a un rango razonable (0-500%)
                            hist_vol = max(0.0, min(5.0, hist_vol))
                        else:
                            app.logger.warning("Desviación estándar de retornos es cero, usando volatilidad por defecto")
                            hist_vol = 0.2
                        
                        app.logger.debug(f"Volatilidad histórica calculada: {hist_vol:.2%}")
                        
                elif historical_prices:
                    app.logger.debug(f"Calculando volatilidad desde {len(historical_prices)} precios")
                    prices = np.array(historical_prices)
                    
                    # Filtrar valores inválidos (NaN, infinitos, no positivos)
                    valid_prices = prices[(~np.isnan(prices)) & (~np.isinf(prices)) & (prices > 0)]
                    
                    if len(valid_prices) < 2:
                        app.logger.warning(f"Precios válidos insuficientes ({len(valid_prices)}), usando volatilidad por defecto")
                        hist_vol = 0.2
                    else:
                        # Calcular retornos logarítmicos
                        returns = np.diff(np.log(valid_prices))
                        
                        # Filtrar retornos inválidos
                        returns = returns[~(np.isnan(returns) | np.isinf(returns))]
                        
                        if len(returns) < 1:
                            app.logger.warning("No se pudieron calcular retornos válidos, usando volatilidad por defecto")
                            hist_vol = 0.2
                        else:
                            std_ret = np.std(returns)
                            if std_ret > 0:
                                hist_vol = float(std_ret * np.sqrt(252))
                                # Limitar volatilidad a un rango razonable
                                hist_vol = max(0.0, min(5.0, hist_vol))
                            else:
                                app.logger.warning("Desviación estándar de retornos es cero, usando volatilidad por defecto")
                                hist_vol = 0.2
                        
                        app.logger.debug(f"Volatilidad histórica calculada: {hist_vol:.2%}")
                else:
                    hist_vol = 0.2  # Default 20%
            
            except Exception as vol_error:
                app.logger.error(f"Error calculando volatilidad histórica: {vol_error}")
                import traceback
                app.logger.error(traceback.format_exc())
                # Usar volatilidad por defecto en caso de error
                hist_vol = 0.2
                app.logger.warning("Usando volatilidad por defecto debido a error en cálculo")
        
        # Validar tiempo hasta expiración (T no puede ser cero)
        T = dte / 365.0
        if T <= 0:
            app.logger.error(f"Tiempo hasta expiración inválido: T={T}")
            return jsonify({'success': False, 'error': 'Days to expiration debe ser mayor que cero'}), 400
        
        # Distribución para el ACTIVO (precio spot)
        try:
            mu = np.log(spot) + (risk_free - 0.5 * hist_vol**2) * T
            sigma = hist_vol * np.sqrt(T)
            
            # Validar que sigma sea válido
            if sigma <= 0 or np.isnan(sigma) or np.isinf(sigma):
                app.logger.error(f"Sigma inválido calculado: {sigma}, usando valor por defecto")
                sigma = hist_vol * np.sqrt(max(T, 1/365))  # Mínimo 1 día
            
            # Rango de precios para el activo
            price_range_asset = np.linspace(spot * 0.5, spot * 1.5, 200)
            pdf_asset = stats.lognorm.pdf(price_range_asset, s=sigma, scale=np.exp(mu))
            cdf_asset = stats.lognorm.cdf(price_range_asset, s=sigma, scale=np.exp(mu))
            
            # Validar resultados
            pdf_asset = np.nan_to_num(pdf_asset, nan=0.0, posinf=0.0, neginf=0.0)
            cdf_asset = np.nan_to_num(cdf_asset, nan=0.0, posinf=1.0, neginf=0.0)
            
            # Estadísticas del activo
            mode_asset = np.exp(mu - sigma**2)
            expected_asset = np.exp(mu + 0.5 * sigma**2)
            median_asset = np.exp(mu)
            
            # Calcular std_asset con protección contra valores inválidos
            try:
                exp_sigma2 = np.exp(sigma**2)
                if exp_sigma2 > 0 and not np.isnan(exp_sigma2) and not np.isinf(exp_sigma2):
                    std_asset = np.sqrt((exp_sigma2 - 1) * np.exp(2*mu + sigma**2))
                    if np.isnan(std_asset) or np.isinf(std_asset) or std_asset <= 0:
                        std_asset = expected_asset * 0.2  # Fallback: 20% del valor esperado
                else:
                    std_asset = expected_asset * 0.2
            except Exception:
                std_asset = expected_asset * 0.2
            
            # Calcular probabilidades con protección
            try:
                prob_itm_call = max(0.0, min(1.0, float(1 - stats.lognorm.cdf(strike, s=sigma, scale=np.exp(mu)))))
                prob_itm_put = max(0.0, min(1.0, float(stats.lognorm.cdf(strike, s=sigma, scale=np.exp(mu)))))
            except Exception as prob_error:
                app.logger.warning(f"Error calculando probabilidades ITM: {prob_error}")
                prob_itm_call = 0.5
                prob_itm_put = 0.5
        
        # Probabilidad en ±1, ±2 desviaciones estándar
            try:
                prob_1std_below = max(0.0, min(1.0, float(stats.lognorm.cdf(expected_asset - std_asset, s=sigma, scale=np.exp(mu)))))
                prob_1std_above = max(0.0, min(1.0, float(1 - stats.lognorm.cdf(expected_asset + std_asset, s=sigma, scale=np.exp(mu)))))
                prob_1std_range = max(0.0, min(1.0, float(1 - prob_1std_below - prob_1std_above)))
        
                prob_2std_below = max(0.0, min(1.0, float(stats.lognorm.cdf(expected_asset - 2*std_asset, s=sigma, scale=np.exp(mu)))))
                prob_2std_above = max(0.0, min(1.0, float(1 - stats.lognorm.cdf(expected_asset + 2*std_asset, s=sigma, scale=np.exp(mu)))))
                prob_2std_range = max(0.0, min(1.0, float(1 - prob_2std_below - prob_2std_above)))
            except Exception as std_prob_error:
                app.logger.warning(f"Error calculando probabilidades de desviaciones estándar: {std_prob_error}")
                prob_1std_below = prob_1std_above = prob_1std_range = 0.33
                prob_2std_below = prob_2std_above = prob_2std_range = 0.33
                
        except Exception as asset_error:
            app.logger.error(f"Error calculando distribución del activo: {asset_error}")
            import traceback
            app.logger.error(traceback.format_exc())
            return jsonify({
                'success': False,
                'error': f'Error al calcular distribución del activo: {str(asset_error)}'
            }), 500
        
        # Distribución para la OPCIÓN (precio teórico)
        # Calcular precio de opción para cada precio spot
        from opciones_comparador import black_scholes_advanced
        option_prices = []
        option_price_range = []
        
        app.logger.debug(f"Calculando precios de opción para {len(price_range_asset)} puntos de precio spot")
        for idx, s in enumerate(price_range_asset):
            try:
                # Validar parámetros antes de calcular
                if s <= 0 or strike <= 0 or T <= 0 or hist_vol < 0:
                    app.logger.debug(f"Parámetros inválidos en punto {idx}: s={s}, strike={strike}, T={T}, vol={hist_vol}")
                    continue
                
                opt_price = black_scholes_advanced(
                    'prima', s, strike, T, risk_free, 0.0,
                    hist_vol, 'call',
                    'accion', ''
                )
                
                # Validar resultado
                if opt_price is None or np.isnan(opt_price) or np.isinf(opt_price) or opt_price < 0:
                    app.logger.debug(f"Precio de opción inválido calculado en punto {idx}: {opt_price}")
                    continue
                
                option_prices.append(float(opt_price))
                option_price_range.append(float(s))
            except Exception as opt_error:
                app.logger.debug(f"Error calculando precio de opción en punto {idx}: {opt_error}")
                continue
        
        app.logger.debug(f"Precios de opción calculados: {len(option_prices)} válidos de {len(price_range_asset)} intentos")
        
        if option_prices and len(option_prices) > 0:
            try:
                option_prices = np.array(option_prices)
                option_price_range = np.array(option_price_range)
                
                # Validar que todos los precios sean positivos
                valid_option_mask = (option_prices > 0) & (~np.isnan(option_prices)) & (~np.isinf(option_prices))
                option_prices = option_prices[valid_option_mask]
                option_price_range = option_price_range[valid_option_mask]
                
                if len(option_prices) < 2:
                    app.logger.warning(f"Precios de opción válidos insuficientes ({len(option_prices)}), omitiendo distribución de opción")
                    option_price_range_dist = []
                    pdf_option = []
                    cdf_option = []
                else:
            # Ajustar distribución lognormal para precios de opción
            # Usar retornos logarítmicos de precios de opción
                    # Proteger contra log(0) usando un offset pequeño
                    min_price = np.min(option_prices)
                    offset = max(1e-10, min_price * 1e-6)  # Offset proporcional al precio mínimo
                    option_returns = np.diff(np.log(option_prices + offset))
                    
                    # Filtrar retornos inválidos
                    option_returns = option_returns[~(np.isnan(option_returns) | np.isinf(option_returns))]
                    
                    if len(option_returns) > 1:
                        option_vol_std = np.std(option_returns)
                        if option_vol_std > 0:
                            option_vol = float(option_vol_std * np.sqrt(252))
                            # Limitar volatilidad de opción
                            option_vol = max(0.0, min(10.0, option_vol))
                        else:
                            app.logger.warning("Desviación estándar de retornos de opción es cero, usando volatilidad base")
                            option_vol = hist_vol * 2
                    else:
                        app.logger.warning("Retornos de opción insuficientes, usando volatilidad base")
                        option_vol = hist_vol * 2
            
                    current_option_price = float(option_prices[-1]) if len(option_prices) > 0 else 0.01
                    
                    # Validar que el precio sea positivo antes de calcular log
                    if current_option_price > 0:
                        mu_option = np.log(max(current_option_price, 0.01)) + (risk_free - 0.5 * option_vol**2) * T
                        sigma_option = option_vol * np.sqrt(max(T, 1/365))  # Proteger contra T=0
                        
                        # Validar sigma_option
                        if sigma_option <= 0 or np.isnan(sigma_option) or np.isinf(sigma_option):
                            app.logger.warning(f"Sigma_option inválido: {sigma_option}, usando valor por defecto")
                            sigma_option = hist_vol * np.sqrt(max(T, 1/365))
                        
                        max_option_price = float(np.max(option_prices))
                        option_price_range_dist = np.linspace(0, max(max_option_price * 2, 0.01), 200)
                        
                        try:
                            pdf_option = stats.lognorm.pdf(option_price_range_dist, s=sigma_option, scale=np.exp(mu_option))
                            cdf_option = stats.lognorm.cdf(option_price_range_dist, s=sigma_option, scale=np.exp(mu_option))
                            
                            # Validar resultados
                            pdf_option = np.nan_to_num(pdf_option, nan=0.0, posinf=0.0, neginf=0.0)
                            cdf_option = np.nan_to_num(cdf_option, nan=0.0, posinf=1.0, neginf=0.0)
                            
                            app.logger.debug(f"Distribución de opción calculada exitosamente")
                        except Exception as dist_error:
                            app.logger.error(f"Error calculando distribución de opción: {dist_error}")
                            option_price_range_dist = []
                            pdf_option = []
                            cdf_option = []
                    else:
                        app.logger.warning("Precio actual de opción no positivo, omitiendo distribución")
                        option_price_range_dist = []
                        pdf_option = []
                        cdf_option = []
            except Exception as option_error:
                app.logger.error(f"Error procesando precios de opción: {option_error}")
                import traceback
                app.logger.error(traceback.format_exc())
                option_price_range_dist = []
                pdf_option = []
                cdf_option = []
        else:
            app.logger.warning("No se calcularon precios de opción válidos")
            option_price_range_dist = []
            pdf_option = []
            cdf_option = []
        
        # Probabilidades
        probabilities = {
            'call_itm': float(prob_itm_call),
            'put_itm': float(prob_itm_put),
            'within_1std': float(prob_1std_range),
            'within_2std': float(prob_2std_range),
            'below_1std': float(prob_1std_below),
            'above_1std': float(prob_1std_above),
            'below_2std': float(prob_2std_below),
            'above_2std': float(prob_2std_above)
        }
        
        result = {
            'success': True,
            'underlying': {
                'prices': price_range_asset.tolist(),
                'pdf': pdf_asset.tolist(),
                'cdf': cdf_asset.tolist(),
                'mode_price': float(mode_asset),
                'expected_price': float(expected_asset),
                'median_price': float(median_asset),
                'volatility': float(hist_vol),
                'spot': float(spot)
            },
            'option': {
                'prices': option_price_range_dist.tolist() if len(option_price_range_dist) > 0 else [],
                'pdf': pdf_option.tolist() if len(pdf_option) > 0 else [],
                'cdf': cdf_option.tolist() if len(cdf_option) > 0 else [],
                'current_price': float(current_option_price) if 'current_option_price' in locals() else 0,
                'strike': float(strike)
            },
            'probabilities': probabilities
        }
        
        app.logger.info("Cálculo de distribución de probabilidad completado exitosamente")
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error inesperado en api_probability_distribution_from_data: {e}")
        import traceback
        error_trace = traceback.format_exc()
        app.logger.error(error_trace)
        return jsonify({
            'success': False,
            'error': f'Error calculando distribución de probabilidad: {str(e)}',
            'details': 'Revise los logs del servidor para más información.'
        }), 500

@app.route('/api/implied_probabilities', methods=['POST'])
@require_auth
def api_implied_probabilities():
    """Calcular probabilidades implícitas ITM/OTM"""
    try:
        data = request.json
        spot = float(data.get('spot'))
        strike = float(data.get('strike'))
        iv = float(data.get('implied_vol', 20)) / 100
        dte = float(data.get('days_to_expiration', 30))
        risk_free = float(data.get('risk_free_rate', 0)) / 100
        
        probs = calcular_probabilidades_implicitas(spot, strike, iv, dte, risk_free)
        
        return jsonify({
            'success': True,
            'probabilities': probs
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# Endpoint de volatilidad histórica (no depende de HAS_STAT_ANALYSIS)
@app.route('/api/historical_volatility', methods=['POST'])
@require_auth
def api_historical_volatility():
    """Calcular volatilidad histórica para múltiples periodos (Close-to-Close o Parkinson)"""
    try:
        data = request.json
        prices = data.get('prices', [])
        returns = data.get('returns', [])
        windows = data.get('windows', [10, 20, 30])
        dates = data.get('dates', [])
        highs = data.get('highs', [])  # Para Parkinson
        lows = data.get('lows', [])    # Para Parkinson
        vol_method = data.get('method', 'close_to_close')  # 'close_to_close' o 'parkinson'
        
        # Logging detallado
        app.logger.info(f"=== API Historical Volatility ===")
        app.logger.info(f"Method: {vol_method}")
        app.logger.info(f"Prices length: {len(prices) if prices else 0}")
        app.logger.info(f"Returns length: {len(returns) if returns else 0}")
        app.logger.info(f"Highs length: {len(highs) if highs else 0}")
        app.logger.info(f"Lows length: {len(lows) if lows else 0}")
        app.logger.info(f"Windows: {windows}")
        app.logger.info(f"First 3 prices: {prices[:3] if prices else 'None'}")
        app.logger.info(f"Last 3 prices: {prices[-3:] if prices else 'None'}")
        
        if not prices and not returns:
            app.logger.error("No prices or returns provided")
            return jsonify({'success': False, 'error': 'Se requieren precios o retornos'}), 400
        
        import pandas as pd
        import numpy as np
        
        # Si tenemos precios pero no retornos, calcularlos
        if prices and not returns:
            prices_arr = np.array(prices)
            returns = np.diff(np.log(prices_arr)).tolist()
            # Ajustar fechas para que coincidan con retornos (usar fechas reales si existen)
            if dates and len(dates) == len(prices_arr):
                dates = dates[1:]
            elif dates and len(dates) >= len(returns):
                dates = dates[-len(returns):]
            else:
                app.logger.warning(f"Generando fechas dummy (no hay suficientes fechas: {len(dates) if dates else 0})")
                dates = [f"Point {i}" for i in range(len(returns))]
        else:
            if dates and len(dates) >= len(returns):
                dates = dates[-len(returns):]
            else:
                app.logger.warning(f"Generando fechas dummy para retornos (fechas: {len(dates) if dates else 0}, retornos: {len(returns)})")
                dates = [f"Point {i}" for i in range(len(returns))]
        
        app.logger.info(f"Fechas ajustadas: {len(dates)} elementos")
        if dates:
            app.logger.info(f"Primera fecha: {dates[0]}, Última fecha: {dates[-1]}")
        
        returns_arr = np.array(returns)
        
        # Verificar datos de retornos
        if len(returns_arr) > 0:
            app.logger.info(f"Returns array stats: min={np.min(returns_arr):.6f}, max={np.max(returns_arr):.6f}, mean={np.mean(returns_arr):.6f}, std={np.std(returns_arr):.6f}")
            app.logger.info(f"First 5 returns: {returns_arr[:5]}")
            app.logger.info(f"Last 5 returns: {returns_arr[-5:]}")
        else:
            app.logger.error("Returns array is empty!")
            return jsonify({'success': False, 'error': 'Returns array is empty'}), 400
        
        # Calcular volatilidades para cada ventana
        volatilities = {}
        dates_result = []
        
        if vol_method == 'parkinson' and highs and lows and len(highs) == len(lows):
            # Volatilidad de Parkinson: σ = √(1/(4n·ln(2)) · Σ[ln(H/L)]²) × √252
            highs_arr = np.array(highs)
            lows_arr = np.array(lows)
            
            # Validar que High > Low
            valid_mask = highs_arr > lows_arr
            if not np.all(valid_mask):
                app.logger.warning(f"Encontrados {np.sum(~valid_mask)} días con High <= Low, usando Close-to-Close")
                vol_method = 'close_to_close'
            else:
                parkinson_factor = 1.0 / (4.0 * np.log(2.0))  # ≈ 0.361
                
                for window in windows:
                    vol_values = []
                    for i in range(len(highs_arr)):
                        start_idx = max(0, i - window + 1)
                        window_highs = highs_arr[start_idx:i+1]
                        window_lows = lows_arr[start_idx:i+1]
                        
                        if len(window_highs) > 1:
                            # Calcular log(High/Low)²
                            hl_ratios = np.log(window_highs / window_lows) ** 2
                            # Volatilidad de Parkinson
                            vol_daily = np.sqrt(parkinson_factor * np.mean(hl_ratios))
                            vol = vol_daily * np.sqrt(252) * 100  # Anualizada en %
                        else:
                            vol = 0
                        vol_values.append(vol)
                        if window == windows[0]:  # Solo una vez las fechas
                            dates_result.append(dates[i] if i < len(dates) else f"Day {i}")
                    volatilities[f'vol_{window}d'] = vol_values
        
        # Fallback o método por defecto: Close-to-Close
        if vol_method == 'close_to_close' or not volatilities:
            app.logger.info(f"Calculando volatilidad Close-to-Close con {len(returns_arr)} retornos")
            for window in windows:
                vol_values = []
                for i in range(len(returns_arr)):
                    start_idx = max(0, i - window + 1)
                    window_returns = returns_arr[start_idx:i+1]
                    if len(window_returns) > 1:
                        vol_std = np.std(window_returns)
                        vol = vol_std * np.sqrt(252) * 100  # Anualizada en %
                        if i == len(returns_arr) - 1:  # Log del último valor
                            app.logger.info(f"Window {window}d: std={vol_std:.6f}, vol_annualized={vol:.2f}%")
                    else:
                        vol = 0
                    vol_values.append(vol)
                    if window == windows[0] and not dates_result:  # Solo una vez las fechas
                        dates_result.append(dates[i] if i < len(dates) else f"Day {i}")
                volatilities[f'vol_{window}d'] = vol_values
                app.logger.info(f"Calculated vol_{window}d: {len(vol_values)} values, first={vol_values[0] if vol_values else 'N/A':.2f}, last={vol_values[-1] if vol_values else 'N/A':.2f}")
        
        # Calcular métricas estadísticas sobre el período más corto (más sensible)
        first_window = windows[0]
        vol_data = volatilities.get(f'vol_{first_window}d', [])
        
        statistics = {}
        if vol_data and len(vol_data) > 0:
            valid_data = [v for v in vol_data if v > 0 and not np.isnan(v)]
            if valid_data:
                statistics = {
                    'mean': float(np.mean(valid_data)),
                    'median': float(np.median(valid_data)),
                    'std': float(np.std(valid_data)),
                    'min': float(np.min(valid_data)),
                    'max': float(np.max(valid_data)),
                    'p25': float(np.percentile(valid_data, 25)),
                    'p50': float(np.percentile(valid_data, 50)),
                    'p75': float(np.percentile(valid_data, 75)),
                    'p95': float(np.percentile(valid_data, 95)),
                    'current': float(valid_data[-1]),
                    'count': len(valid_data)
                }
                app.logger.info(f"Statistics: mean={statistics['mean']:.2f}%, current={statistics['current']:.2f}%")
        
        app.logger.info(f"Returning {len(volatilities)} volatility series with statistics")
        return jsonify({
            'success': True,
            'dates': dates_result,
            'volatilities': volatilities,
            'statistics': statistics,
            'method': vol_method
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/volatility_skew', methods=['POST'])
@require_auth
def api_volatility_skew():
    """
    API: Volatility Skew - Calcula volatilidad implícita para múltiples strikes
    Versión corregida y securitizada
    """
    try:
        import numpy as np
        data = request.json
        
        # Validación y sanitización de inputs
        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibieron datos'
            }), 400
        
        # Validar campos requeridos
        required_fields = ['spot', 'maturity', 'risk_free_rate', 'strikes_with_prices']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Campo requerido faltante: {field}'
                }), 400
        
        # Validar y convertir tipos
        try:
            spot = float(data['spot'])
            maturity_days = float(data['maturity'])
            risk_free_rate = float(data['risk_free_rate'])
            strikes_with_prices = data['strikes_with_prices']
        except (ValueError, TypeError) as e:
            return jsonify({
                'success': False,
                'error': f'Error en tipos de datos: {str(e)}'
            }), 400
        
        # Validar rangos razonables
        if spot <= 0 or spot > 1000000:
            return jsonify({
                'success': False,
                'error': 'Spot price debe ser positivo y menor a 1,000,000'
            }), 400
        
        if maturity_days <= 0 or maturity_days > 3650:
            return jsonify({
                'success': False,
                'error': 'Maturity debe ser positivo y menor a 3650 días'
            }), 400
        
        if not isinstance(strikes_with_prices, list) or len(strikes_with_prices) == 0:
            return jsonify({
                'success': False,
                'error': 'strikes_with_prices debe ser una lista no vacía'
            }), 400
        
        if len(strikes_with_prices) > 100:
            return jsonify({
                'success': False,
                'error': 'Máximo 100 strikes permitidos'
            }), 400
        
        # Convertir días a años
        T = maturity_days / 365.0
        r = risk_free_rate / 100.0
        q = 0.0  # Sin dividendos por defecto
        asset_type = data.get('asset_type', 'stock')
        settlement_style = data.get('settlement_style', '')
        
        # Calcular IV para cada strike
        skew_data = []
        
        for strike_info in strikes_with_prices:
            try:
                # Validar estructura del strike
                if not isinstance(strike_info, dict):
                    continue
                
                strike = float(strike_info.get('strike', 0))
                call_price = strike_info.get('call_price')
                put_price = strike_info.get('put_price')
                
                # Validar strike
                if strike <= 0 or strike > 1000000:
                    continue
                
                result_item = {
                    'strike': strike,
                    'iv_call': None,
                    'iv_put': None
                }
                
                # Calcular IV Call si hay precio
                if call_price is not None:
                    try:
                        call_price_float = float(call_price)
                        if call_price_float > 0 and call_price_float < spot * 2:
                            iv_call = black_scholes_vol_impl(
                                spot, strike, T, r, q,
                                call_price_float, 'call',
                                asset_type, settlement_style
                            )
                            if not (np.isnan(iv_call) or np.isinf(iv_call) or iv_call <= 0 or iv_call > 5.0):
                                result_item['iv_call'] = float(iv_call)
                    except Exception as e:
                        # Si falla el cálculo, dejar como None
                        pass
                
                # Calcular IV Put si hay precio
                if put_price is not None:
                    try:
                        put_price_float = float(put_price)
                        if put_price_float > 0 and put_price_float < spot * 2:
                            iv_put = black_scholes_vol_impl(
                                spot, strike, T, r, q,
                                put_price_float, 'put',
                                asset_type, settlement_style
                            )
                            if not (np.isnan(iv_put) or np.isinf(iv_put) or iv_put <= 0 or iv_put > 5.0):
                                result_item['iv_put'] = float(iv_put)
                    except Exception as e:
                        # Si falla el cálculo, dejar como None
                        pass
                
                # Solo agregar si tiene al menos una IV válida
                if result_item['iv_call'] is not None or result_item['iv_put'] is not None:
                    skew_data.append(result_item)
            
            except Exception as e:
                # Continuar con el siguiente strike si hay error
                continue
        
        if len(skew_data) == 0:
            return jsonify({
                'success': False,
                'error': 'No se pudo calcular volatilidad implícita para ningún strike'
            }), 400
        
        return jsonify({
            'success': True,
            'skew_data': skew_data,
            'summary': {
                'total_strikes': len(skew_data),
                'calls_with_iv': sum(1 for s in skew_data if s['iv_call'] is not None),
                'puts_with_iv': sum(1 for s in skew_data if s['iv_put'] is not None)
            }
        })
    
    except Exception as e:
            import traceback
            return jsonify({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 400

@app.route('/api/volatility_smile', methods=['POST'])
@require_auth
def api_volatility_smile():
    """
    API: Volatility Smile - Calcula volatilidad implícita usando Black-Scholes (bisección)
    Permite al usuario ingresar inputs (S, K, T, r, sigma) y precios de mercado opcionales
    """
    try:
        import numpy as np
        import math
        
        data = request.json
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibieron datos'
            }), 400
        
        # Helpers Black-Scholes
        def normal_pdf(x):
            return math.exp(-(x ** 2) / 2.0) / math.sqrt(2.0 * math.pi)

        def normal_cdf(x):
            a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
            k = 1.0 / (1.0 + 0.2316419 * abs(x))
            poly = ((((a5 * k + a4) * k + a3) * k + a2) * k + a1) * k
            approx = 1.0 - normal_pdf(x) * poly
            return approx if x >= 0 else 1.0 - approx

        def black_scholes_value(parametro, s, k, T, r, q, sigma, call_put, tipo_subyacente, estilo_liquidacion):
            parametro = parametro.lower()
            call_put = call_put.lower()
            tipo_subyacente = tipo_subyacente.lower()
            estilo_liquidacion = (estilo_liquidacion or "").lower()

            if tipo_subyacente == "futuro":
                if estilo_liquidacion not in ["futures_style", "equity_style"]:
                    raise ValueError("Indicar estilo de liquidación: 'futures_style' o 'equity_style'")
                b = 0.0
                if estilo_liquidacion == "futures_style":
                    r = 0.0
            elif tipo_subyacente == "accion":
                b = r - q
            else:
                raise ValueError("tipo_subyacente debe ser 'accion' o 'futuro'")

            if T <= 0:
                payoff = max(s - k, 0.0) if call_put == "call" else max(k - s, 0.0)
                delta = 1.0 if (call_put == "call" and s > k) else (-1.0 if (call_put == "put" and s < k) else 0.0)
                return payoff if parametro == "prima" else (delta if parametro == "delta" else 0.0)

            d1 = (math.log(s / k) + (b + sigma ** 2 / 2.0) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            df_b = math.exp((b - r) * T)
            df_r = math.exp(-r * T)

            if call_put == "call":
                prima = s * df_b * normal_cdf(d1) - k * df_r * normal_cdf(d2)
            else:
                prima = k * df_r * normal_cdf(-d2) - s * df_b * normal_cdf(-d1)

            return prima if parametro == "prima" else prima

        def black_scholes_vol_impl(s, k, T, r, q, prima, call_put, tipo_subyacente, estilo_liquidacion):
            if prima <= 0 or T <= 0:
                return 0.0
            low, high = 0.0, 4.0
            epsilon = 0.0001
            counter = 0
            while (high - low) > epsilon:
                counter += 1
                if counter > 100:
                    return np.nan
                mid = (high + low) / 2.0
                val = black_scholes_value("prima", s, k, T, r, q, mid, call_put, tipo_subyacente, estilo_liquidacion)
                if val > prima:
                    high = mid
                else:
                    low = mid
            return (high + low) / 2.0

        # Validar y obtener inputs
        spot = float(data.get('spot', 0))
        strikes = data.get('strikes', [])
        maturity = float(data.get('maturity', 0))  # En años
        risk_free_rate = float(data.get('risk_free_rate', 0))  # Decimal
        initial_volatility = float(data.get('initial_volatility', 0.2))  # Decimal
        binomial_steps = int(data.get('binomial_steps', 100))
        market_prices = data.get('market_prices', {'calls': {}, 'puts': {}})
        dividend_yield = float(data.get('dividend_yield', 0.0))
        tipo_subyacente = data.get('tipo_subyacente', 'accion')
        estilo_liquidacion = data.get('estilo_liquidacion', '')
        
        # Validaciones
        if spot <= 0:
            return jsonify({
                'success': False,
                'error': 'El precio del subyacente (S) debe ser mayor a 0'
            }), 400
        
        if maturity <= 0:
            return jsonify({
                'success': False,
                'error': 'El tiempo a vencimiento (T) debe ser mayor a 0'
            }), 400
        
        if not strikes or len(strikes) == 0:
            return jsonify({
                'success': False,
                'error': 'Se requiere al menos un strike'
            }), 400
        
        if binomial_steps < 10 or binomial_steps > 500:
            return jsonify({
                'success': False,
                'error': 'El número de pasos binomiales debe estar entre 10 y 500'
            }), 400
        
        # Convertir strikes a floats y ordenarlos
        strikes = sorted([float(s) for s in strikes if float(s) > 0])
        
        callsIV = []
        putsIV = []
        valid_strikes = []
        
        # Calcular volatilidad implícita para cada strike
        for strike in strikes:
            call_iv = None
            put_iv = None
            
            # Verificar si hay precio de mercado para este strike
            strike_str = str(int(strike)) if strike == int(strike) else str(strike)
            call_market_price = market_prices.get('calls', {}).get(strike_str) or market_prices.get('calls', {}).get(str(strike))
            put_market_price = market_prices.get('puts', {}).get(strike_str) or market_prices.get('puts', {}).get(str(strike))
            
            # Calcular IV Call usando método inverso Black-Scholes
            if call_market_price is not None:
                try:
                    call_price = float(call_market_price)
                    if call_price > 0:
                        call_iv = black_scholes_vol_impl(
                            spot, strike, maturity, risk_free_rate, dividend_yield,
                            call_price, 'call', tipo_subyacente, estilo_liquidacion
                        )
                        if np.isnan(call_iv) or call_iv <= 0 or call_iv > 5.0:
                            call_iv = initial_volatility
                except Exception as e:
                    print(f"Error calculando IV Call para strike {strike}: {e}")
                    call_iv = initial_volatility
            else:
                # Si no hay precio de mercado, usar volatilidad inicial para calcular precio teórico
                try:
                    theo_call_price = black_scholes_value(
                        'prima', spot, strike, maturity, risk_free_rate, dividend_yield,
                        initial_volatility, 'call', tipo_subyacente, estilo_liquidacion
                    )
                    if theo_call_price > 0:
                        call_iv = black_scholes_vol_impl(
                            spot, strike, maturity, risk_free_rate, dividend_yield,
                            theo_call_price, 'call', tipo_subyacente, estilo_liquidacion
                        )
                        if np.isnan(call_iv) or call_iv <= 0 or call_iv > 5.0:
                            call_iv = initial_volatility  # Fallback a volatilidad inicial
                except Exception as e:
                    print(f"Error calculando precio teórico Call para strike {strike}: {e}")
                    call_iv = initial_volatility
            
            # Calcular IV Put usando método inverso Black-Scholes
            if put_market_price is not None:
                try:
                    put_price = float(put_market_price)
                    if put_price > 0:
                        put_iv = black_scholes_vol_impl(
                            spot, strike, maturity, risk_free_rate, dividend_yield,
                            put_price, 'put', tipo_subyacente, estilo_liquidacion
                        )
                        if np.isnan(put_iv) or put_iv <= 0 or put_iv > 5.0:
                            put_iv = initial_volatility
                except Exception as e:
                    print(f"Error calculando IV Put para strike {strike}: {e}")
                    put_iv = initial_volatility
            else:
                try:
                    theo_put_price = black_scholes_value(
                        'prima', spot, strike, maturity, risk_free_rate, dividend_yield,
                        initial_volatility, 'put', tipo_subyacente, estilo_liquidacion
                    )
                    if theo_put_price > 0:
                        put_iv = black_scholes_vol_impl(
                            spot, strike, maturity, risk_free_rate, dividend_yield,
                            theo_put_price, 'put', tipo_subyacente, estilo_liquidacion
                        )
                        if np.isnan(put_iv) or put_iv <= 0 or put_iv > 5.0:
                            put_iv = initial_volatility  # Fallback a volatilidad inicial
                except Exception as e:
                    print(f"Error calculando precio teórico Put para strike {strike}: {e}")
                    put_iv = initial_volatility
            
            # Solo agregar si al menos una IV es válida
            if call_iv is not None or put_iv is not None:
                valid_strikes.append(float(strike))
                callsIV.append(float(call_iv * 100) if call_iv is not None else None)  # Convertir a porcentaje
                putsIV.append(float(put_iv * 100) if put_iv is not None else None)  # Convertir a porcentaje
        
        if len(valid_strikes) == 0:
            return jsonify({
                'success': False,
                'error': 'No se pudo calcular volatilidad implícita para ningún strike'
            }), 400
        
        return jsonify({
            'success': True,
            'data': {
                'strikes': valid_strikes,
                'callsIV': callsIV,
                'putsIV': putsIV,
                'currentPrice': float(spot),
                'maturity': float(maturity),
                'riskFreeRate': float(risk_free_rate * 100),  # En porcentaje
                'binomialSteps': binomial_steps
            }
        })
    
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 400

@app.route('/api/iv/binomial', methods=['POST'])
@require_auth
def api_iv_binomial():
    """Calcula IV con modelo binomial americano (bisección) para una fila."""
    try:
        import math
        from opciones_comparador import binomial_vol_impl
        data = request.json or {}

        spot = float(data.get('spot', 0))
        strike = float(data.get('strike', 0))
        maturity_days = float(data.get('maturity_days', 0))
        risk_free_rate = float(data.get('risk_free_rate', 0))
        price = float(data.get('price', 0))
        option_type = data.get('option_type', 'call')
        binomial_steps = int(data.get('binomial_steps', 100))
        dividend_yield = float(data.get('dividend_yield', 0))
        tipo_subyacente = data.get('tipo_subyacente', 'accion')
        estilo_liquidacion = data.get('estilo_liquidacion', '')

        if spot <= 0 or strike <= 0:
            return jsonify({'success': False, 'error': 'Spot y Strike deben ser mayores a 0'}), 400
        if maturity_days <= 0:
            return jsonify({'success': False, 'error': 'El vencimiento debe ser mayor a 0'}), 400
        if price <= 0:
            return jsonify({'success': True, 'iv': None})
        if binomial_steps < 10 or binomial_steps > 500:
            return jsonify({'success': False, 'error': 'Pasos binomiales inválidos'}), 400

        # Validar límites teóricos para evitar IV inválida
        T = maturity_days / 365.0
        if option_type == 'call':
            intrinsic = max(spot - strike, 0.0)
            upper_bound = spot
        else:
            intrinsic = max(strike - spot, 0.0)
            upper_bound = strike

        if price < intrinsic or price > upper_bound:
            return jsonify({'success': True, 'iv': None})

        q = dividend_yield
        iv = binomial_vol_impl(
            spot, strike, T, risk_free_rate, q,
            price, option_type, 'americana', binomial_steps,
            tipo_subyacente, estilo_liquidacion
        )

        if hasattr(iv, 'item'):
            iv = float(iv.item())

        if iv is None or (isinstance(iv, float) and (math.isnan(iv) or iv <= 0 or iv > 5.0)):
            return jsonify({'success': True, 'iv': None})

        return jsonify({'success': True, 'iv': float(iv)})
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 400

# Screener de acciones

@app.route('/screener')
@require_auth
def screener_page():
    """Página del screener de acciones"""
    return render_template('screener.html')

@app.route('/api/screener/scan', methods=['POST'])
@require_auth
@rate_limit
def api_screener_scan():
        """Screener de acciones con filtros"""
        try:
            data = request.json
            filters = data.get('filters', {})
            
            # Lista de símbolos a analizar (puedes expandir esto)
            symbols = data.get('symbols', ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX'])
            
            if isinstance(symbols, str):
                symbols = [s.strip() for s in symbols.split(',')]
            
            results = []
            
            for symbol in symbols:
                try:
                    if HAS_STAT_ANALYSIS:
                        # Descargar datos
                        from datetime import datetime, timedelta
                        start_date = datetime.now() - timedelta(days=365)
                        df = descargar_datos(symbol, start=start_date, interval='1d')
                        if df is None or df.empty:
                            continue
                        
                        # Calcular métricas
                        retornos = calcular_retornos(df)
                        vol_historica = calcular_volatilidad_historica(retornos, window=30)
                        current_price = df['Close'].iloc[-1]
                        avg_volume = df['Volume'].tail(30).mean()
                        price_change_1d = ((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
                        price_change_1m = ((df['Close'].iloc[-1] - df['Close'].iloc[-30]) / df['Close'].iloc[-30]) * 100 if len(df) >= 30 else None
                        
                        # Aplicar filtros
                        passes = True
                        
                        if filters.get('min_price') and current_price < filters['min_price']:
                            passes = False
                        if filters.get('max_price') and current_price > filters['max_price']:
                            passes = False
                        if filters.get('min_volatility') and vol_historica < filters['min_volatility']:
                            passes = False
                        if filters.get('max_volatility') and vol_historica > filters['max_volatility']:
                            passes = False
                        if filters.get('min_volume') and avg_volume < filters['min_volume']:
                            passes = False
                        if filters.get('min_change_1d') and price_change_1d < filters['min_change_1d']:
                            passes = False
                        if filters.get('max_change_1d') and price_change_1d > filters['max_change_1d']:
                            passes = False
                        
                        if passes:
                            results.append({
                                'symbol': symbol,
                                'price': round(current_price, 2),
                                'volatility': round(vol_historica * 100, 2),
                                'volume': int(avg_volume),
                                'change_1d': round(price_change_1d, 2),
                                'change_1m': round(price_change_1m, 2) if price_change_1m else None,
                                'high_52w': round(df['High'].tail(252).max(), 2) if len(df) >= 252 else round(df['High'].max(), 2),
                                'low_52w': round(df['Low'].tail(252).min(), 2) if len(df) >= 252 else round(df['Low'].min(), 2),
                            })
                    else:
                        # Fallback básico sin análisis estadístico
                        results.append({
                            'symbol': symbol,
                            'price': None,
                            'volatility': None,
                            'volume': None,
                            'change_1d': None,
                            'change_1m': None,
                            'high_52w': None,
                            'low_52w': None,
                        })
                except Exception as e:
                    continue
            
            return jsonify({
                'success': True,
                'results': results,
                'count': len(results)
            })
        except Exception as e:
            import traceback
            return jsonify({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 400
    
# Estadísticas del mercado
@app.route('/statistics')
@require_auth
def statistics_page():
    """Página de estadísticas del mercado"""
    return render_template('statistics.html')

@app.route('/api/statistics/market', methods=['POST'])
@require_auth
@rate_limit
def api_market_statistics():
    """Obtener estadísticas del mercado"""
    try:
        data = request.json
        symbol = data.get('symbol', 'SPY')  # Default S&P 500
        period = data.get('period', '1y')
        
        if HAS_STAT_ANALYSIS:
            # Convertir period a start date
            from datetime import datetime, timedelta
            period_days = {'1d': 1, '5d': 5, '1mo': 30, '3mo': 90, '6mo': 180, '1y': 365, '2y': 730, '5y': 1825, '10y': 3650, 'ytd': 365, 'max': 3650}
            days = period_days.get(period, 365)
            start_date = datetime.now() - timedelta(days=days)
            df = descargar_datos(symbol, start=start_date, interval=interval or '1d')
            if df is None or df.empty:
                return jsonify({'success': False, 'error': 'No se pudieron descargar datos'}), 400
            
            retornos = calcular_retornos(df)
            vol_historica = calcular_volatilidad_historica(retornos, window=30)
            expected_move = calcular_expected_move(df['Close'].iloc[-1], vol_historica, 30)
            
            # Calcular estadísticas
            current_price = df['Close'].iloc[-1]
            high_52w = df['High'].tail(252).max() if len(df) >= 252 else df['High'].max()
            low_52w = df['Low'].tail(252).min() if len(df) >= 252 else df['Low'].min()
            price_from_52w_high = ((current_price - high_52w) / high_52w) * 100
            price_from_52w_low = ((current_price - low_52w) / low_52w) * 100
            
            # Distribución de retornos
            import numpy as np
            returns_array = retornos.dropna().values
            
            stats = {
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'volatility_30d': round(vol_historica * 100, 2),
                'expected_move_30d': round(expected_move, 2),
                'high_52w': round(high_52w, 2),
                'low_52w': round(low_52w, 2),
                'price_from_52w_high': round(price_from_52w_high, 2),
                'price_from_52w_low': round(price_from_52w_low, 2),
                'avg_volume_30d': int(df['Volume'].tail(30).mean()),
                'returns_stats': {
                    'mean': round(np.mean(returns_array) * 100, 2),
                    'std': round(np.std(returns_array) * 100, 2),
                    'min': round(np.min(returns_array) * 100, 2),
                    'max': round(np.max(returns_array) * 100, 2),
                    'skewness': round(float(retornos.skew()), 2),
                    'kurtosis': round(float(retornos.kurtosis()), 2),
                },
                'price_changes': {
                    '1d': round(((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100, 2),
                    '5d': round(((df['Close'].iloc[-1] - df['Close'].iloc[-6]) / df['Close'].iloc[-6]) * 100, 2) if len(df) >= 6 else None,
                    '1m': round(((df['Close'].iloc[-1] - df['Close'].iloc[-30]) / df['Close'].iloc[-30]) * 100, 2) if len(df) >= 30 else None,
                    '3m': round(((df['Close'].iloc[-1] - df['Close'].iloc[-90]) / df['Close'].iloc[-90]) * 100, 2) if len(df) >= 90 else None,
                    '1y': round(((df['Close'].iloc[-1] - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100, 2),
                }
            }
            
            return jsonify({'success': True, 'statistics': stats})
        else:
            return jsonify({'success': False, 'error': 'Módulo de análisis estadístico no disponible'}), 503
    except Exception as e:
            import traceback
            return jsonify({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 400
    
# Análisis de rentabilidad de estrategias (no depende de HAS_STAT_ANALYSIS)
@app.route('/api/strategies/analyze', methods=['POST'])
@require_auth
@rate_limit
def api_analyze_strategy():
    """Analizar rentabilidad y ratios de una estrategia - Soporta TODAS las estrategias"""
    try:
        # Intentar importar la instancia global primero
        profitability_analyzer = None
        try:
            from core.profitability import profitability_analyzer
            # Si es None, crear una nueva instancia
            if profitability_analyzer is None:
                from core.profitability import ProfitabilityAnalyzer
                profitability_analyzer = ProfitabilityAnalyzer()
        except (ImportError, AttributeError) as import_err:
            # Fallback: importar la clase y crear instancia
            try:
                from core.profitability import ProfitabilityAnalyzer
                profitability_analyzer = ProfitabilityAnalyzer()
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Error importando ProfitabilityAnalyzer: {str(e)}. Error original: {str(import_err)}'
                }), 500
        
        data = request.json
        strategy_type = data.get('strategy_type')
        strategy_params = data.get('params', {})
        
        if not HAS_PORTFOLIO:
            return jsonify({'success': False, 'error': 'Portfolio modules not available'}), 503
        
        # Parámetros base
        spot = float(strategy_params.get('spot', 100))
        expiration_days = float(strategy_params.get('expiration_days', 30))
        risk_free_rate = float(strategy_params.get('risk_free_rate', 0.05))
        volatility = float(strategy_params.get('volatility', 0.20))
        quantity = int(strategy_params.get('quantity', 1))
        asset_type = strategy_params.get('asset_type', 'stock')
        dividend_yield = float(strategy_params.get('dividend_yield', 0.0))
        model = strategy_params.get('model', 'black-scholes')
        binomial_steps = int(strategy_params.get('binomial_steps', 100))
        settlement_style = strategy_params.get('settlement_style', '')
        
        # Crear posiciones según el tipo de estrategia
        positions = []
        
        if strategy_type == 'single':
            strike = float(strategy_params.get('strike', spot))
            option_type = strategy_params.get('option_type', 'call')
            market_price = float(strategy_params.get('market_price', 0))
            positions = StrategyBuilder.create_single_option(
                spot, strike, expiration_days, risk_free_rate, volatility,
                option_type, asset_type, dividend_yield, model, binomial_steps,
                quantity, market_price, settlement_style
            )
        
        elif strategy_type == 'bull_call_spread':
            lower_strike = float(strategy_params.get('lower_strike', spot * 0.95))
            upper_strike = float(strategy_params.get('upper_strike', spot * 1.05))
            market_prices = strategy_params.get('market_prices')
            if market_prices and isinstance(market_prices, (list, tuple)):
                market_prices = tuple(market_prices[:2])
            positions = StrategyBuilder.create_bull_call_spread(
                spot, lower_strike, upper_strike, expiration_days,
                risk_free_rate, volatility, asset_type, dividend_yield,
                model, binomial_steps, quantity, market_prices, settlement_style
            )
        
        elif strategy_type == 'bear_call_spread':
            lower_strike = float(strategy_params.get('lower_strike', spot * 0.95))
            upper_strike = float(strategy_params.get('upper_strike', spot * 1.05))
            market_prices = strategy_params.get('market_prices')
            if market_prices and isinstance(market_prices, (list, tuple)):
                market_prices = tuple(market_prices[:2])
            positions = StrategyBuilder.create_bear_call_spread(
                spot, lower_strike, upper_strike, expiration_days,
                risk_free_rate, volatility, asset_type, dividend_yield,
                model, binomial_steps, quantity, market_prices, settlement_style
            )
        
        elif strategy_type == 'bull_put_spread':
            lower_strike = float(strategy_params.get('lower_strike', spot * 0.95))
            upper_strike = float(strategy_params.get('upper_strike', spot * 1.05))
            market_prices = strategy_params.get('market_prices')
            if market_prices and isinstance(market_prices, (list, tuple)):
                market_prices = tuple(market_prices[:2])
            positions = StrategyBuilder.create_bull_put_spread(
                spot, lower_strike, upper_strike, expiration_days,
                risk_free_rate, volatility, asset_type, dividend_yield,
                model, binomial_steps, quantity, market_prices, settlement_style
            )
        
        elif strategy_type == 'bear_put_spread':
            lower_strike = float(strategy_params.get('lower_strike', spot * 0.95))
            upper_strike = float(strategy_params.get('upper_strike', spot * 1.05))
            market_prices = strategy_params.get('market_prices')
            if market_prices and isinstance(market_prices, (list, tuple)):
                market_prices = tuple(market_prices[:2])
            positions = StrategyBuilder.create_bear_put_spread(
                spot, lower_strike, upper_strike, expiration_days,
                risk_free_rate, volatility, asset_type, dividend_yield,
                model, binomial_steps, quantity, market_prices, settlement_style
            )
        
        elif strategy_type == 'straddle':
            strike = float(strategy_params.get('strike', spot))
            market_prices = strategy_params.get('market_prices')
            if market_prices and isinstance(market_prices, (list, tuple)):
                market_prices = tuple(market_prices[:2])
            positions = StrategyBuilder.create_straddle(
                spot, strike, expiration_days, risk_free_rate, volatility,
                asset_type, dividend_yield, model, binomial_steps,
                quantity, market_prices, settlement_style
            )
        
        elif strategy_type == 'strangle':
            lower_strike = float(strategy_params.get('lower_strike', spot * 0.95))
            upper_strike = float(strategy_params.get('upper_strike', spot * 1.05))
            market_prices = strategy_params.get('market_prices')
            if market_prices and isinstance(market_prices, (list, tuple)):
                market_prices = tuple(market_prices[:2])
            positions = StrategyBuilder.create_strangle(
                spot, lower_strike, upper_strike, expiration_days,
                risk_free_rate, volatility, asset_type, dividend_yield,
                model, binomial_steps, quantity, market_prices, settlement_style
            )
        
        elif strategy_type == 'iron_condor':
            lower_put_strike = float(strategy_params.get('lower_put_strike', spot * 0.90))
            lower_call_strike = float(strategy_params.get('lower_call_strike', spot * 0.95))
            upper_call_strike = float(strategy_params.get('upper_call_strike', spot * 1.05))
            upper_put_strike = float(strategy_params.get('upper_put_strike', spot * 1.10))
            market_prices = strategy_params.get('market_prices')
            if market_prices and isinstance(market_prices, (list, tuple)):
                market_prices = tuple(market_prices[:4])
            positions = StrategyBuilder.create_iron_condor(
                spot, lower_put_strike, lower_call_strike, upper_call_strike, upper_put_strike,
                expiration_days, risk_free_rate, volatility, asset_type, dividend_yield,
                model, binomial_steps, quantity, market_prices, settlement_style
            )
        
        elif strategy_type == 'calendar_spread':
            strike = float(strategy_params.get('strike', spot))
            near_expiration = float(strategy_params.get('near_expiration', expiration_days * 0.5))
            market_prices = strategy_params.get('market_prices')
            if market_prices and isinstance(market_prices, (list, tuple)):
                market_prices = tuple(market_prices[:2])
            positions = StrategyBuilder.create_calendar_spread(
                spot, strike, near_expiration, expiration_days,
                risk_free_rate, volatility, asset_type, dividend_yield,
                model, binomial_steps, quantity, market_prices, settlement_style
            )
        
        elif strategy_type == 'call_butterfly':
            lower_strike = float(strategy_params.get('lower_strike', spot * 0.90))
            middle_strike = float(strategy_params.get('middle_strike', spot))
            upper_strike = float(strategy_params.get('upper_strike', spot * 1.10))
            market_prices = strategy_params.get('market_prices')
            if market_prices and isinstance(market_prices, (list, tuple)):
                market_prices = tuple(market_prices[:3])
            positions = StrategyBuilder.create_call_butterfly(
                spot, lower_strike, middle_strike, upper_strike, expiration_days,
                risk_free_rate, volatility, asset_type, dividend_yield,
                model, binomial_steps, quantity, market_prices, settlement_style
            )
        
        elif strategy_type == 'put_butterfly':
            lower_strike = float(strategy_params.get('lower_strike', spot * 0.90))
            middle_strike = float(strategy_params.get('middle_strike', spot))
            upper_strike = float(strategy_params.get('upper_strike', spot * 1.10))
            market_prices = strategy_params.get('market_prices')
            if market_prices and isinstance(market_prices, (list, tuple)):
                market_prices = tuple(market_prices[:3])
            positions = StrategyBuilder.create_put_butterfly(
                spot, lower_strike, middle_strike, upper_strike, expiration_days,
                risk_free_rate, volatility, asset_type, dividend_yield,
                model, binomial_steps, quantity, market_prices, settlement_style
            )
        
        elif strategy_type == 'protective_put':
            put_strike = float(strategy_params.get('put_strike', spot * 0.95))
            stock_price = float(strategy_params.get('stock_price', spot))
            put_price = float(strategy_params.get('put_price', 0))
            positions = StrategyBuilder.create_protective_put(
                spot, put_strike, expiration_days, risk_free_rate, volatility,
                asset_type, dividend_yield, model, binomial_steps,
                quantity, (stock_price, put_price), settlement_style
            )
        
        elif strategy_type == 'protective_call':
            call_strike = float(strategy_params.get('call_strike', spot * 1.05))
            stock_price = float(strategy_params.get('stock_price', spot))
            call_price = float(strategy_params.get('call_price', 0))
            positions = StrategyBuilder.create_protective_call(
                spot, call_strike, expiration_days, risk_free_rate, volatility,
                asset_type, dividend_yield, model, binomial_steps,
                quantity, (stock_price, call_price), settlement_style
            )
        
        elif strategy_type == 'covered_call':
            call_strike = float(strategy_params.get('call_strike', spot * 1.05))
            stock_price = float(strategy_params.get('stock_price', spot))
            call_price = float(strategy_params.get('call_price', 0))
            positions = StrategyBuilder.create_covered_call(
                spot, call_strike, expiration_days, risk_free_rate, volatility,
                asset_type, dividend_yield, model, binomial_steps,
                quantity, (stock_price, call_price), settlement_style
            )
        
        elif strategy_type == 'covered_put':
            put_strike = float(strategy_params.get('put_strike', spot * 0.95))
            stock_price = float(strategy_params.get('stock_price', spot))
            put_price = float(strategy_params.get('put_price', 0))
            positions = StrategyBuilder.create_covered_put(
                spot, put_strike, expiration_days, risk_free_rate, volatility,
                asset_type, dividend_yield, model, binomial_steps,
                quantity, (stock_price, put_price), settlement_style
            )
        
        elif strategy_type == 'collar':
            put_strike = float(strategy_params.get('put_strike', spot * 0.95))
            call_strike = float(strategy_params.get('call_strike', spot * 1.05))
            market_prices = strategy_params.get('market_prices')
            if market_prices and isinstance(market_prices, (list, tuple)):
                market_prices = tuple(market_prices[:3])
            positions = StrategyBuilder.create_collar(
                spot, put_strike, call_strike, expiration_days,
                risk_free_rate, volatility, asset_type, dividend_yield,
                model, binomial_steps, quantity, market_prices, settlement_style
            )
        
        elif strategy_type == 'delta_hedge':
            option_strike = float(strategy_params.get('strike', spot))
            option_type = strategy_params.get('option_type', 'call')
            market_price = float(strategy_params.get('market_price', 0))
            positions = StrategyBuilder.create_delta_hedge(
                spot, option_strike, expiration_days, risk_free_rate, volatility,
                option_type, asset_type, dividend_yield, model, binomial_steps,
                quantity, market_price, settlement_style
            )
        
        elif strategy_type == 'delta_gamma_hedge':
            option_strike = float(strategy_params.get('strike', spot))
            hedge_option_strike = float(strategy_params.get('hedge_option_strike', spot * 1.05))
            option_type = strategy_params.get('option_type', 'call')
            hedge_option_type = strategy_params.get('hedge_option_type', '')
            market_prices = strategy_params.get('market_prices')
            if market_prices and isinstance(market_prices, (list, tuple)):
                market_prices = tuple(market_prices[:2])
            positions = StrategyBuilder.create_delta_gamma_hedge(
                spot, option_strike, hedge_option_strike, expiration_days,
                risk_free_rate, volatility, option_type, hedge_option_type,
                asset_type, dividend_yield, model, binomial_steps,
                quantity, market_prices, settlement_style
            )
        
        else:
            return jsonify({
                'success': False,
                'error': f'Estrategia no soportada: {strategy_type}'
            }), 400
            
        # Analizar rentabilidad usando el analizador genérico para TODAS las estrategias
        if not positions:
            return jsonify({
                'success': False,
                'error': 'No se pudieron crear posiciones para la estrategia'
            }), 400
        
        if profitability_analyzer is None:
            return jsonify({
                'success': False,
                'error': 'ProfitabilityAnalyzer no está disponible. Verifica que core.profitability esté correctamente importado.'
            }), 500
        
        analysis = profitability_analyzer.analyze_strategy(positions, spot, strategy_type)
        
        return jsonify({'success': True, 'analysis': analysis})
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 400

# Datos para TradingView
@app.route('/api/chart/data', methods=['POST'])
@require_auth
@rate_limit
def api_chart_data():
    """Obtener datos de precio para gráficos TradingView"""
    try:
        data = request.json
        symbol = data.get('symbol', 'AAPL')
        period = data.get('period', '1y')
        interval = data.get('interval', '1d')
        
        if HAS_STAT_ANALYSIS:
            # Convertir period a start date
            from datetime import datetime, timedelta
            period_days = {'1d': 1, '5d': 5, '1mo': 30, '3mo': 90, '6mo': 180, '1y': 365, '2y': 730, '5y': 1825, '10y': 3650, 'ytd': 365, 'max': 3650}
            days = period_days.get(period, 365)
            start_date = datetime.now() - timedelta(days=days)
            df = descargar_datos(symbol, start=start_date, interval='1d')
            if df is None or df.empty:
                return jsonify({'success': False, 'error': 'No se pudieron descargar datos'}), 400
            
            # Convertir a formato TradingView
            chart_data = []
            for idx, row in df.iterrows():
                chart_data.append({
                    'time': idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume']) if 'Volume' in row else 0
                })
            
            return jsonify({
                'success': True,
                'data': chart_data,
                'symbol': symbol
            })
        else:
            return jsonify({'success': False, 'error': 'Módulo de análisis estadístico no disponible'}), 503
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 400

    # Resumen de Mercado (página unificada)
    
    @app.route('/api/calendar/events', methods=['POST'])
    @require_auth
    @rate_limit
    def api_calendar_events():
        """Obtener eventos del calendario económico"""
        try:
            data = request.json or {}
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            country = data.get('country', 'US')  # US, EU, etc.
            
            # Por ahora, simulamos eventos económicos importantes
            # En producción, usarías una API como TradingEconomics, Alpha Vantage, etc.
            from datetime import datetime, timedelta
            import random
            
            if not start_date:
                start_date = datetime.now().strftime('%Y-%m-%d')
            if not end_date:
                end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            # Eventos económicos comunes
            event_templates = [
                {'name': 'PIB Trimestral', 'impact': 'high', 'category': 'GDP'},
                {'name': 'Tasa de Desempleo', 'impact': 'high', 'category': 'Employment'},
                {'name': 'IPC (Inflación)', 'impact': 'high', 'category': 'Inflation'},
                {'name': 'Tasa de Interés', 'impact': 'high', 'category': 'Interest Rate'},
                {'name': 'Ventas Minoristas', 'impact': 'medium', 'category': 'Retail'},
                {'name': 'Confianza del Consumidor', 'impact': 'medium', 'category': 'Consumer'},
                {'name': 'Producción Industrial', 'impact': 'medium', 'category': 'Industrial'},
                {'name': 'Balance Comercial', 'impact': 'medium', 'category': 'Trade'},
                {'name': 'Ventas de Vivienda', 'impact': 'low', 'category': 'Housing'},
                {'name': 'Pedidos de Bienes Duraderos', 'impact': 'low', 'category': 'Durable Goods'},
            ]
            
            events = []
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            current = start
            
            while current <= end:
                # Agregar algunos eventos aleatorios
                if random.random() < 0.3:  # 30% de probabilidad de evento por día
                    template = random.choice(event_templates)
                    hour = random.randint(8, 16)  # Horario de mercado
                    event_time = current.replace(hour=hour, minute=0)
                    
                    events.append({
                        'date': event_time.strftime('%Y-%m-%d'),
                        'time': event_time.strftime('%H:%M'),
                        'name': template['name'],
                        'country': country,
                        'impact': template['impact'],
                        'category': template['category'],
                        'forecast': round(random.uniform(-2, 5), 2),
                        'previous': round(random.uniform(-1, 4), 2),
                    })
                
                current += timedelta(days=1)
            
            # Ordenar por fecha
            events.sort(key=lambda x: (x['date'], x['time']))
            
            return jsonify({
                'success': True,
                'events': events,
                'count': len(events),
                'start_date': start_date,
                'end_date': end_date
            })
        except Exception as e:
            import traceback
            return jsonify({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 400
    
    # Mapa macro (mantener para compatibilidad)
    @app.route('/macro')
    @require_auth
    def macro_page():
        """Página de mapa macro"""
        return redirect(url_for('market_overview_page'))
    
    @app.route('/api/macro/data', methods=['POST'])
    @require_auth
    @rate_limit
    def api_macro_data():
        """Obtener datos macroeconómicos"""
        try:
            from datetime import datetime
            import random
            
            data = request.json or {}
            country = data.get('country', 'US')
            indicators = data.get('indicators', ['gdp', 'inflation', 'unemployment', 'interest_rate'])
            
            macro_data = {}
            
            try:
                import yfinance as yf
                import pandas as pd
                
                # Mapeo de países a tickers
                country_tickers = {
                    'US': {'index': '^GSPC', 'bond': '^TNX', 'currency': 'DX-Y.NYB'},
                    'EU': {'index': '^FCHI', 'bond': '^FVX', 'currency': 'EURUSD=X'},
                    'UK': {'index': '^FTSE', 'bond': '^IRX', 'currency': 'GBPUSD=X'},
                    'JP': {'index': '^N225', 'bond': '^TNX', 'currency': 'JPY=X'},
                }
                
                tickers = country_tickers.get(country, country_tickers['US'])
                
                # Obtener datos de índices
                if 'gdp' in indicators or 'index' in indicators:
                    try:
                        index_ticker = yf.Ticker(tickers['index'])
                        hist = index_ticker.history(period='1y')
                        if not hist.empty and len(hist) > 0:
                            current_price = float(hist['Close'].iloc[-1])
                            change_1d = 0
                            change_1y = 0
                            volatility = 0
                            
                            if len(hist) > 1:
                                prev_price = float(hist['Close'].iloc[-2])
                                if prev_price > 0:
                                    change_1d = ((current_price - prev_price) / prev_price) * 100
                            
                            if len(hist) > 0:
                                first_price = float(hist['Close'].iloc[0])
                                if first_price > 0:
                                    change_1y = ((current_price - first_price) / first_price) * 100
                            
                            pct_changes = hist['Close'].pct_change()
                            if not pct_changes.empty:
                                volatility = float(pct_changes.std() * 100)
                            
                            macro_data['index'] = {
                                'current': current_price,
                                'change_1d': change_1d,
                                'change_1y': change_1y,
                                'volatility': volatility,
                            }
                    except Exception as e:
                        print(f"Error obteniendo índice: {e}")
                        pass
                
                # Obtener tasas de interés (bonos)
                if 'interest_rate' in indicators:
                    try:
                        bond_ticker = yf.Ticker(tickers['bond'])
                        hist = bond_ticker.history(period='1y')
                        if not hist.empty and len(hist) > 0:
                            current_rate = float(hist['Close'].iloc[-1])
                            change_1d = 0
                            if len(hist) > 1:
                                change_1d = float(hist['Close'].iloc[-1] - hist['Close'].iloc[-2])
                            
                            macro_data['interest_rate'] = {
                                'current': current_rate,
                                'change_1d': change_1d,
                            }
                    except Exception as e:
                        print(f"Error obteniendo tasa de interés: {e}")
                        pass
                
                # Obtener tipo de cambio
                if 'currency' in indicators:
                    try:
                        currency_ticker = yf.Ticker(tickers['currency'])
                        hist = currency_ticker.history(period='1y')
                        if not hist.empty and len(hist) > 0:
                            current_rate = float(hist['Close'].iloc[-1])
                            change_1d = 0
                            if len(hist) > 1:
                                prev_rate = float(hist['Close'].iloc[-2])
                                if prev_rate > 0:
                                    change_1d = ((current_rate - prev_rate) / prev_rate) * 100
                            
                            macro_data['currency'] = {
                                'current': current_rate,
                                'change_1d': change_1d,
                            }
                    except Exception as e:
                        print(f"Error obteniendo tipo de cambio: {e}")
                        pass
                
                # Datos simulados para indicadores que no están disponibles directamente
                if 'gdp' in indicators:
                    macro_data['gdp'] = {
                        'current': round(random.uniform(2.0, 4.5), 2),
                        'forecast': round(random.uniform(2.5, 5.0), 2),
                        'previous': round(random.uniform(1.5, 4.0), 2),
                    }
                
                if 'inflation' in indicators:
                    macro_data['inflation'] = {
                        'current': round(random.uniform(1.5, 3.5), 2),
                        'forecast': round(random.uniform(2.0, 3.0), 2),
                        'previous': round(random.uniform(1.0, 3.0), 2),
                    }
                
                if 'unemployment' in indicators:
                    macro_data['unemployment'] = {
                        'current': round(random.uniform(3.0, 6.0), 2),
                        'forecast': round(random.uniform(3.5, 5.5), 2),
                        'previous': round(random.uniform(3.5, 6.5), 2),
                    }
                
            except Exception as e:
                pass
            
            return jsonify({
                'success': True,
                'country': country,
                'data': macro_data,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            import traceback
            return jsonify({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 400
    
    @app.route('/api/macro/map', methods=['POST'])
    @require_auth
    @rate_limit
    def api_macro_map():
        """Obtener datos macroeconómicos de múltiples países para el mapa"""
        try:
            from datetime import datetime
            import random
            
            data = request.json or {}
            indicator_type = data.get('indicator', 'interest_rate')  # interest_rate, inflation, gdp
            date = data.get('date', None)  # Para timeline histórico (opcional)
            
            # Mapeo de códigos de países ISO a datos
            # En producción, esto vendría de una API real o base de datos
            country_data = {
                'US': {'name': 'Estados Unidos', 'interest_rate': 5.25, 'inflation': 3.2, 'gdp': 2.1},
                'CA': {'name': 'Canadá', 'interest_rate': 5.0, 'inflation': 2.8, 'gdp': 1.8},
                'MX': {'name': 'México', 'interest_rate': 11.25, 'inflation': 4.7, 'gdp': 3.2},
                'BR': {'name': 'Brasil', 'interest_rate': 10.5, 'inflation': 4.6, 'gdp': 2.5},
                'AR': {'name': 'Argentina', 'interest_rate': 133.0, 'inflation': 160.0, 'gdp': -2.0},
                'GB': {'name': 'Reino Unido', 'interest_rate': 5.25, 'inflation': 3.9, 'gdp': 0.5},
                'DE': {'name': 'Alemania', 'interest_rate': 4.5, 'inflation': 3.7, 'gdp': -0.3},
                'FR': {'name': 'Francia', 'interest_rate': 4.5, 'inflation': 3.2, 'gdp': 0.9},
                'IT': {'name': 'Italia', 'interest_rate': 4.5, 'inflation': 0.8, 'gdp': 0.3},
                'ES': {'name': 'España', 'interest_rate': 4.5, 'inflation': 3.5, 'gdp': 2.5},
                'JP': {'name': 'Japón', 'interest_rate': -0.1, 'inflation': 2.5, 'gdp': 1.9},
                'CN': {'name': 'China', 'interest_rate': 3.45, 'inflation': 0.1, 'gdp': 5.2},
                'IN': {'name': 'India', 'interest_rate': 6.5, 'inflation': 5.0, 'gdp': 7.2},
                'AU': {'name': 'Australia', 'interest_rate': 4.35, 'inflation': 4.1, 'gdp': 2.1},
                'NZ': {'name': 'Nueva Zelanda', 'interest_rate': 5.5, 'inflation': 4.7, 'gdp': 1.8},
                'KR': {'name': 'Corea del Sur', 'interest_rate': 3.5, 'inflation': 2.6, 'gdp': 3.1},
                'RU': {'name': 'Rusia', 'interest_rate': 16.0, 'inflation': 7.4, 'gdp': 3.6},
                'ZA': {'name': 'Sudáfrica', 'interest_rate': 8.25, 'inflation': 5.5, 'gdp': 0.4},
                'TR': {'name': 'Turquía', 'interest_rate': 45.0, 'inflation': 64.3, 'gdp': 4.5},
                'CH': {'name': 'Suiza', 'interest_rate': 1.75, 'inflation': 1.4, 'gdp': 0.8},
                'NO': {'name': 'Noruega', 'interest_rate': 4.5, 'inflation': 5.5, 'gdp': 0.5},
                'SE': {'name': 'Suecia', 'interest_rate': 4.0, 'inflation': 2.3, 'gdp': -0.8},
            }
            
            # Agregar datos simulados para más países
            european_countries = ['BE', 'NL', 'AT', 'PT', 'GR', 'IE', 'FI', 'DK', 'PL', 'CZ', 'HU', 'RO']
            for code in european_countries:
                if code not in country_data:
                    country_data[code] = {
                        'name': f'País {code}',
                        'interest_rate': round(random.uniform(3.0, 6.0), 2),
                        'inflation': round(random.uniform(1.5, 4.5), 2),
                        'gdp': round(random.uniform(0.5, 3.0), 2)
                    }
            
            # Preparar respuesta con datos del indicador seleccionado
            map_data = {}
            for country_code, data_dict in country_data.items():
                value = data_dict.get(indicator_type, 0)
                map_data[country_code] = {
                    'name': data_dict['name'],
                    'value': value,
                    'code': country_code
                }
            
            # Definir rangos de colores según el tipo de indicador
            all_values = [d['value'] for d in map_data.values()]
            min_val = min(all_values) if all_values else 0
            max_val = max(all_values) if all_values else 100
            
            return jsonify({
                'success': True,
                'indicator': indicator_type,
                'data': map_data,
                'ranges': {
                    'min': min_val,
                    'max': max_val
                },
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            import traceback
            return jsonify({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }), 400

if __name__ == '__main__':
    # Ejecutar backup automático al iniciar (solo en producción)
    try:
        run_startup_backup()
    except Exception as backup_error:
        print(f"⚠️  Error en backup de inicio: {backup_error}")
    
    # Wrapper global para capturar cualquier error
    try:
        import socket
        
        def find_free_port():
            """Encuentra un puerto libre"""
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', 0))
                    s.listen(1)
                    port = s.getsockname()[1]
                return port
            except Exception as e:
                print(f"[ERROR] Error encontrando puerto libre: {e}")
                return 5000  # Fallback
        
        # Intentar puerto 5000, si está ocupado usar otro
        port = 5000
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', port))
            sock.close()
        except OSError:
            print(f"⚠️ Puerto {port} ocupado, buscando puerto libre...")
            port = find_free_port()
            print(f"✓ Usando puerto {port}")
        
        print("\n" + "="*70)
        print("WEB APP - ANÁLISIS DE OPCIONES")
        print("="*70)
        
        if USERS:
            print("\n✅ Usuarios configurados:")
            for username in USERS.keys():
                print(f"   - {username}")
            if len(USERS) == 3 and 'admin' in USERS and 'trader' in USERS and 'analyst' in USERS:
                # Si son los usuarios por defecto, mostrar advertencia
                if USERS['admin'] == hash_password('admin123'):
                    print("\n⚠️  ADVERTENCIA: Estas usando claves por defecto!")
                    print("   Para produccion, modifica las claves en app_clean.py")
                    print("   (líneas ~125-130) o usa variables de entorno.")
        else:
            print("\n⚠️  No hay usuarios configurados")
        
        print(f"\n🌐 http://localhost:{port}/login")
        print("="*70 + "\n")
        
        print(f"\n⚠️ IMPORTANTE: El servidor se está iniciando...")
        print(f"   Espera ver: '* Running on http://0.0.0.0:{port}'")
        print(f"   Si no aparece, hay un error.\n")
        
        try:
            print(f"⏳ Iniciando Flask en puerto {port}...\n")
            print(f"✓ Servidor Flask iniciado correctamente")
            print(f"✓ Escuchando en: http://0.0.0.0:{port}")
            try:
                print(f"✓ Templates en: {template_dir if 'template_dir' in locals() else 'templates'}\n")
            except:
                print(f"✓ Templates en: templates\n")
            print("="*70)
            print("🚀 SERVIDOR FLASK INICIADO - MANTÉN ESTA CELDA EJECUTÁNDOSE")
            print("="*70 + "\n")
            
            # En Colab, Flask debe mantenerse corriendo
            # debug=False es importante para evitar problemas de reinicio
            app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
        except KeyboardInterrupt:
            print("\n\n✓ Servidor detenido por el usuario")
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"\n⚠️ Puerto {port} ocupado. Intentando otro puerto...")
                port = find_free_port()
                print(f"✓ Usando puerto {port}")
                print(f"🌐 http://localhost:{port}/login\n")
                app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
            else:
                print(f"\n✗ Error OSError: {e}")
                import traceback
                traceback.print_exc()
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            print(f"\n⚠️ Si ves este error, comparte el mensaje completo arriba")
            # Mantener proceso vivo para diagnóstico
            print("⚠️  Manteniendo proceso vivo para diagnóstico...")
            import time
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                pass
    except Exception as e:
        print(f"\n✗ ERROR CRÍTICO AL INICIAR: {e}")
        import traceback
        traceback.print_exc()
        print(f"\n⚠️ Si ves este error, comparte el mensaje completo arriba")
        # Mantener proceso vivo para diagnóstico
        print("⚠️  Manteniendo proceso vivo para diagnóstico...")
        import time
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass

