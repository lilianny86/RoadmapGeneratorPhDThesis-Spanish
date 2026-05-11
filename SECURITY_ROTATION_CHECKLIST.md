# SECURITY CHECKLIST (SEC-01 / SEC-02)

## Objetivo
- Rotar credenciales SMTP potencialmente expuestas.
- Operar solo con secretos en variables de entorno (`.env` local o vault).

## SEC-01 | Rotación de credenciales SMTP
1. Identificar la cuenta SMTP comprometida o histórica.
2. Revocar contraseña anterior o token anterior en el proveedor.
3. Generar una nueva contraseña de aplicación/token.
4. Confirmar que la credencial antigua quedó inválida.
5. Registrar fecha de rotación y responsable.

## SEC-02 | Migración a entorno seguro
1. Copiar `.env.example` a `.env` en entorno local.
2. Cargar secretos reales solo en `.env` local (o gestor de secretos).
3. Verificar que `.env` esté excluido en `.gitignore`.
4. Ejecutar chequeo:
   - `python run_roadmap.py --company-type small --target-level 3 --answers-file examples\\answers_small.json --security-check`
5. Si el chequeo marca secretos hardcodeados, corregir antes de continuar.

## Criterio de cierre
- No hay secretos hardcodeados detectados por `--security-check`.
- SMTP configurado por entorno cuando `ROADMAP_REQUIRE_SMTP=1`.
- Rotación registrada en bitácora interna del proyecto.
