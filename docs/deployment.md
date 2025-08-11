# Syvrona: Deploying Updates to Production

This guide outlines the steps for deploying changes to the Syvrona application on the production DigitalOcean Droplet.

## 🧭 Deployment Architecture Overview

* The application is deployed as Docker containers on a DigitalOcean Ubuntu droplet.
* All containers (including the app and MySQL) run as **non-root users** inside the container.
* The application directory is managed as a Git repository.
* SSH keys are used for both server access and GitHub authentication.
* No source code or bind-mounts are used in production containers—code is baked into the image.

## Key Operational Points

* Always deploy using the production-safe `docker-compose.yml` (no bind mounts or dev settings).
* Use the `-f` flag explicitly if you have `docker-compose.override.yml` present, e.g.:

``` bash
docker compose -f docker-compose.yml up -d --build
    
```

* Never deploy with `docker-compose.override.yml` active in production.
* All updates should be tested locally before deploying to prod.

## 📝 Step-by-Step Deployment

### 1. Push Local Changes to GitHub

Ensure all local changes are committed:

``` bash
git add .
git commit -m "Describe your update"
git push origin master
```

### 2. SSH into the Production Droplet and Change to Syvrona Directory

``` bash
ssh appuser@your.droplet.ip
cd syvrona-ai/
```

### 3. Put site in Maintenance Mode

``` bash
touch /srv/maintenance/enabled
```

### 4. Bring Down Containers

``` bash
docker compose down
```

### 5. Pull Latest Code from GitHub

``` bash
git pull
```

### 6. Rebuild and Restart the App

``` bash
docker compose -f docker-compose.yml up -d --build
```

### 7. Apply Database Migrations

``` bash
# Login to container:
docker exec -it syvrona-ai-web-1 bash
# run command
flask db upgrade
```

### 8. Put Site in Live/Prod Mode

``` bash
rm /srv/maintenance/enabled
```

### 9. Verify the Deployment

* Visit: <https://syvrona.com/>
* Confirm new fixes and funtionality

### 10. Check Logs (if needed)

``` bash
docker ps
docker logs syvrona-ai-web-1
```

## 🔐 Security and User Permissions

* The app container runs as a dedicated non-root user (`appuser` or similar).
* App files and log files in `/app` are owned by the non-root user.
* MySQL container persists data via Docker volumes (never bind-mounts).
* Do **not** run Docker as root; ensure `appuser` is in the `docker` group.

## Backup Prod MySQL

1. Login to production server and run commands:

    ```bash
    # ssh to prod
    ssh appuser@syvrona.com

    # change to syvrona-ai directory
    cd syvrona-ai

    # excecute backup (prod)
    docker exec syvrona-ai-mysql-1 mysqldump -u root -p'yourpassword' --all-databases --routines --events --triggers --single-transaction > /home/appuser/syvrona_backup_$(date +%F_%H-%M-%S).sql

    # development
    docker exec syvrona-ai-mysql-1 mysqldump -u root -p'yourpassword' --all-databases --routines --events --triggers --single-transaction > /Volumes/termondttech/Syvrona/database-backups/dev/syvrona_backup_$(date +%F_%H-%M-%S).sql
    ```

2. From local Machine (when backing up remote server)

    ```bash
    # copy file down to network storage array
    scp appuser@syvrona.com:/home/appuser/syvrona_backup_$(date +%F_%H-%M-%S).sql /Volumes/termondttech/Syvrona/database-backups/prod
    ```

## Restore Procedure (Best Practice)

Restore should be tested in staging before production!

```bash
# Copy backup file to the server:
scp /path/to/your/network/storage/backupfilename youruser@your.droplet.ip.address:~/

#Copy file into the container:
docker cp ~/backupfilename syvrona-ai-mysql-1:/tmp/

#Import backup (inside the container):
docker exec -it syvrona-ai-mysql-1 bash
mysql -u root -p < /tmp/backupfilename
exit

#Clean up imported file:

docker exec syvrona-ai-mysql-1 rm /tmp/backupfilename
rm ~/backupfilename
```

## Troubleshooting Checklist

* **App container fails to start:**

1. Check logs:

``` bash
docker compose logs -f web
```

1. Most common: file permissions or database connectivity.

* **Git pull fails (permission denied):**

1. Confirm SSH key is present and registered with GitHub.
1. Test with

``` bash
ssh -T git@github.com
```

* **Permission denied writing files:**

1. Ensure no bind mounts override container file permissions.
1. Check file ownership inside container (`whoami`, `ls -l /app`).

## Best Practices Summary

* Do all dev with bind mounts and overrides locally, never in production.
* Only deploy production-hardened compose and Dockerfile settings to prod.
* Keep secrets out of git; use environment variables or Docker secrets as appropriate.
* Always review updates and test locally before pushing to production.

## References

* [Docker Compose Documentation](https://docs.docker.com/compose/ )
* [GitHub SSH Docs](https://docs.github.com/en/authentication/connecting-to-github-with-ssh )
* [Docker Security Best Practices](https://docs.docker.com/engine/security/ )
