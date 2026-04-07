# Verwende ein Node.js-Image als Basis
FROM node:20-alpine

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Kopiere package.json und package-lock.json (falls vorhanden)
COPY package*.json ./

# Installiere Abhängigkeiten
RUN npm install

# Kopiere den Rest des Quellcodes
COPY . .

# Exponiere Port 4200
EXPOSE 4200

# Starte den Entwicklungsserver auf Port 4200
CMD ["npx", "ng", "serve", "--port", "4200", "--host", "0.0.0.0"]
