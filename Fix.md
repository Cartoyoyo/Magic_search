# Fix - Magic Search

| Date | Problème | Correction |
|------|----------|------------|
| 2026-04-07 | La table d'attributs s'ouvrait derrière Magic Search. | `_maybe_raise()` vérifie maintenant que la fenêtre active est bien QGIS avant de remonter le widget. |
| 2026-04-08 | La barre restait flottante à l'écran quand QGIS était réduit. | `StayOnTopEventFilter` écoute `WindowStateChange` et masque/restaure le widget avec la fenêtre QGIS. |
| 2026-04-10 | Le widget ne suivait pas QGIS lors d'un déplacement ou redimensionnement de la fenêtre. | `StayOnTopEventFilter` écoute `QEvent.Move` sur la fenêtre principale et déclenche un repositionnement ; idem après restauration depuis la barre des tâches. |
