"""
Publie le plugin sur plugins.qgis.org via l'API XML-RPC.
Appele par le workflow GitHub Actions .github/workflows/publish-qgis.yml
uniquement sur un tag de version (vX.Y.Z) qui doit correspondre a la
version declaree dans metadata.txt (verifie avant tout upload).

Variables d'environnement attendues :
  OSGEO_USERNAME, OSGEO_PASSWORD - identifiants du compte OSGeo
  GITHUB_REF_NAME                - fourni automatiquement par GitHub Actions (ex: v1.2.0)
"""
import configparser
import os
import re
import sys
import zipfile
import xmlrpc.client

PLUGIN_NAME = 'magic_search'
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METADATA_PATH = os.path.join(REPO_ROOT, 'metadata.txt')
EXCLUDE_DIRS = {'.git', '.github', '__pycache__', 'tests', 'scripts'}
EXCLUDE_FILES = {'.gitignore'}
# Documentation de developpement : inutile dans le plugin installe
EXCLUDE_SUFFIXES = ('.pyc', '.zip', '.d2', '.svg')


def read_metadata_version():
    with open(METADATA_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            m = re.match(r'^version\s*=\s*(.+)$', line.strip())
            if m:
                return m.group(1).strip()
    raise RuntimeError("Impossible de trouver 'version=' dans metadata.txt")


def check_metadata_parses():
    """Relit metadata.txt comme le fait plugins.qgis.org.

    Le serveur le charge avec configparser, interpolation activee : un '%'
    isole dans le changelog ou la description fait echouer l'upload apres
    coup, avec un message peu lisible. Autant s'en apercevoir ici, avant de
    construire le ZIP.
    """
    parser = configparser.ConfigParser()
    try:
        parser.read(METADATA_PATH, encoding='utf-8')
        for key in parser['general']:
            parser['general'][key]
    except configparser.Error as exc:
        raise RuntimeError(
            "metadata.txt est illisible pour plugins.qgis.org : %s\n"
            "Un '%%' isole doit etre double ('%%%%') ou reformule." % exc
        )


def check_tag_matches_version(tag_name, metadata_version):
    tag_version = tag_name.lstrip('v')
    if tag_version != metadata_version:
        raise RuntimeError(
            f"Le tag '{tag_name}' (version {tag_version}) ne correspond pas "
            f"a la version declaree dans metadata.txt ({metadata_version}). "
            f"Corrigez metadata.txt ou le tag avant de publier."
        )


def build_zip(version):
    zip_path = os.path.join(REPO_ROOT, f'{PLUGIN_NAME}.{version}.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(REPO_ROOT):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fname in files:
                if fname in EXCLUDE_FILES or fname.endswith(EXCLUDE_SUFFIXES):
                    continue
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, REPO_ROOT).replace(os.sep, '/')
                zf.write(full, f'{PLUGIN_NAME}/{rel}')
    return zip_path


def upload(zip_path, username, password):
    with open(zip_path, 'rb') as f:
        zip_data = f.read()
    server = xmlrpc.client.ServerProxy(
        f'https://{username}:{password}@plugins.qgis.org/plugins/RPC2/'
    )
    result = server.plugin.upload(xmlrpc.client.Binary(zip_data))
    print(f'Upload OK : {result}')


def main():
    username = os.environ.get('OSGEO_USERNAME')
    password = os.environ.get('OSGEO_PASSWORD')
    tag_name = os.environ.get('GITHUB_REF_NAME')

    if not username or not password:
        print('OSGEO_USERNAME / OSGEO_PASSWORD manquants (secrets GitHub non configures).', file=sys.stderr)
        sys.exit(1)
    if not tag_name:
        print('GITHUB_REF_NAME manquant (ce script doit etre lance depuis un tag).', file=sys.stderr)
        sys.exit(1)

    check_metadata_parses()
    metadata_version = read_metadata_version()
    check_tag_matches_version(tag_name, metadata_version)

    zip_path = build_zip(metadata_version)
    print(f'ZIP cree : {zip_path} ({os.path.getsize(zip_path) / 1024:.1f} Ko)')

    upload(zip_path, username, password)


if __name__ == '__main__':
    main()
