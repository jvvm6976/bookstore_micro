def get_database_config():
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ecommerce_product',
        'USER': 'postgres',
        'PASSWORD': 'root',
        'HOST': 'db-postgres',
        'PORT': '5432',
    }
