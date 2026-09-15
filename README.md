# StremBox-Plugin

**An open-source [Stremio](https://stremio.com/) add-on to stream French public domain torrents using your own Bauxite seedbox.**

Please note that while this add-on is currently only working for French content, the documentation is only available in English. This is because I believe that code documentation should always be written in English, as I may expand the software to support other languages later.
User documentation will be available in French soon directly in the app.

## Table of Contents

- [Features](#features)
- [Local Installation](#local-installation)
  - [Prerequisites](#prerequisites)
  - [Steps](#steps)
- [Self-Hosting](#self-hosting)
  - [Prerequisites](#prerequisites)
  - [Steps](#steps)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## Features

- **Bauxite integration**: Add and stream torrents from your own Bauxite seedbox directly from the Stremio interface.
- **French Movies**: Movies from the french public domain.
- **Passthrough Streaming**: Stream torrents while they're being downloaded by your Bauxite seedbox (fast forward may not work properly using this feature).
- **No Local Torrenting**: No local torrenting is required; torrents are streamed directly from your Bauxite seedbox.

## Local Installation

### Prerequisites

- Docker compose
- A [Bauxite](https://codeberg.org/Philamand/Bauxite) instance up and running
- [Astral UV](https://github.com/astral-sh/uv) installed on your machine
- [dbmate](https://github.com/amacneil/dbmate) installed on your machine

### Steps

1. Clone the repository:

   ```bash
   git clone https://codeberg.org/Philamand/StremBox-Plugin
   ```

2. Navigate to the project directory:

   ```bash
   cd StremBox-Plugin
   ```

3. Copy the `.uv.env.example` to `.uv.env` and update the values as needed:

   ```bash
   cp .uv.env.example .uv.env
   ```

4. Copy the `.env.example` to `.env` and update the values as needed:

   ```bash
   cp .env.example .env
   ```

5. Run the Docker compose command to start the development services:

   ```bash
   docker compose -f docker-compose.dev.yml up -d
   ```

6. Run the tests:

   ```bash
   uv run --env-file .uv.env pytest
   ```

7. Run the migrations:

   ```bash
   dbmate up
   ```

8. Run the development server:
   ```bash
   uv run --env-file .uv.env fastapi dev
   ```

## Self-Hosting

### Prerequisites

- Docker compose
- A [Bauxite](https://codeberg.org/Philamand/Bauxite) instance up and running

### Steps

1. Clone the repository:

   ```bash
   git clone https://codeberg.org/Philamand/StremBox-Plugin
   ```

2. Navigate to the project directory:

   ```bash
   cd StremBox-Plugin
   ```

3. Copy the `.env.example` to `.env` and update the values as needed:

   ```bash
   cp .env.example .env
   nano .env
   ```

4. Copy the `Caddyfile.example` to `Caddyfile` and update the values as needed:

   ```bash
   cp Caddyfile.example Caddyfile
   ```

5. Run the Docker compose command to start the services:

   ```bash
   docker compose up -d
   ```

6. Access the LibreBox UI by navigating to `https://<your-domain>` in your browser.

## Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository.
2. Create a new branch (git checkout -b feature/your-feature).
3. Commit your changes (git commit -am 'Add some feature').
4. Push to the branch (git push origin feature/your-feature).
5. Open a Pull Request.

For major changes, please open an issue first to discuss what you would like to change.

You can use AI to help you with code generation and documentation, but please carefully review and test the generated code before committing. **Do not commit AI generated code without understanding what it does and why it was generated.**

## License

This project is licensed under the AGPL License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [Frenchio](https://github.com/aymene69/frenchio): Most of the torrent-related codebase is based on Frenchio.
