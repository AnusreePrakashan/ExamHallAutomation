import os

class Config:
    SECRET_KEY = 'your-secret-key-here'
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = 'Nettur@123'  # Add your MySQL password
    MYSQL_DB = 'exam_seating'
    MYSQL_CURSORCLASS = 'DictCursor'