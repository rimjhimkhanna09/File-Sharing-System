# Secure File Sharing System

A secure file sharing system that allows two types of users:
1. Operations Users (Ops Users)
2. Client Users

## Features

- User Authentication (Signup/Login)
- Email Verification
- Secure File Upload (Ops Users only)
- Secure File Download (Client Users only)
- File Listing
- JWT-based Authentication
- Secure URL Generation

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
uvicorn main:app --reload
```

## API Endpoints

### Authentication
- POST `/signup` - Create new user account
- POST `/token` - Get access token
- POST `/verify-email/{token}` - Verify user email

### File Operations
- POST `/upload-file/` - Upload file (Ops Users only)
- GET `/download-file/{file_id}` - Get download link (Ops Users only)
- GET `/download/{token}` - Download file (Client Users only)
- GET `/files` - List all files

## Security Features

1. File Type Restriction: Only pptx, docx, and xlsx files allowed
2. Role-based Access Control:
   - Ops Users can upload files
   - Client Users can download files
3. Secure URL Generation:
   - URLs are encrypted and unique
   - Only accessible by client users
4. JWT Authentication:
   - All endpoints require valid JWT token
   - Tokens expire after 30 minutes
5. Email Verification:
   - New users must verify email before login
   - Verification link sent via email

## Testing

Run tests using pytest:
```bash
pytest tests/
```

## Deployment

For detailed deployment instructions, see the [Deployment Guide](docs/deployment_guide.md).

### Quick Start

1. Copy the example environment file and set your configuration:
```bash
cp .env.example .env
```

2. Build and run the containers:
```bash
docker-compose up --build
```

The application will be available at `http://localhost:8000`.

### Production Deployment

For production deployment, follow these steps:

1. Set up environment variables:
```bash
export SECRET_KEY='your-secret-key'
export SMTP_SERVER='smtp.gmail.com'
export SMTP_PORT=587
export SMTP_EMAIL='your-email@gmail.com'
export SMTP_PASSWORD='your-app-specific-password'
```

2. Create production Docker image:
```bash
docker build -t fileshare:production .
```

3. Run the production container:
```bash
docker run -d -p 8000:8000 \
  -e DATABASE_URL=postgresql://fileshare:fileshare@db:5432/fileshare \
  -e SECRET_KEY=${SECRET_KEY} \
  -e SMTP_SERVER=${SMTP_SERVER} \
  -e SMTP_PORT=${SMTP_PORT} \
  -e SMTP_EMAIL=${SMTP_EMAIL} \
  -e SMTP_PASSWORD=${SMTP_PASSWORD} \
  -v /path/to/uploads:/app/uploads \
  fileshare:production
```

### Nginx Configuration

Here's a sample Nginx configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /uploads/ {
        alias /app/uploads/;
        autoindex off;
    }
}
```

### SSL/TLS

1. Obtain SSL certificates using Let's Encrypt:
```bash
sudo certbot certonly --webroot -w /var/www/html -d your-domain.com
```

2. Set up automatic renewal:
```bash
sudo certbot renew --dry-run
```

### Monitoring

1. Set up logging:
```bash
sudo docker logs -f fileshare_app_1
```

2. Monitor database:
```bash
sudo docker exec -it fileshare_db_1 psql -U fileshare -d fileshare
```

## Environment Variables

The following environment variables need to be set:

```bash
DATABASE_URL=postgresql://user:password@host:port/dbname
SECRET_KEY=your-secret-key
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password
```

## File Structure

```
file-sharing-system/
├── main.py          # Main FastAPI application
├── tests/           # Test files
├── requirements.txt # Python dependencies
└── README.md        # Project documentation
```
# File-Sharing-System
