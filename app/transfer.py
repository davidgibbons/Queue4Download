"""
File transfer module for Q4D client.
Handles LFTP-based file transfers via SFTP.
"""
import os
import subprocess # nosec B404
import shutil
import logging

logger = logging.getLogger("Transfer")

# Transfer constants
HOSTKEYFIX = "set sftp:auto-confirm yes"


class FileTransfer:  # pylint: disable=too-few-public-methods
    """Handles file transfers using LFTP over SFTP."""

    def __init__(self, config, type_to_dir):
        """Initialize file transfer handler with configuration and type mappings."""
        self.config = config
        self.type_to_dir = type_to_dir
        logger.debug("FileTransfer initialized with %d type mappings", len(type_to_dir))
        logger.debug("Transfer config - host: %s, threads: %d, segments: %d",
                     config.host, config.threads, config.segments)

    def transfer_file(self, target, hash_, typecode):  # pylint: disable=too-many-branches,too-many-statements
        """Transfer a file or directory using lftp. Returns True on success."""
        logger.debug("Starting transfer - target: %s, hash: %s, typecode: %s",
                     target, hash_, typecode)

        # Map typecode to directory
        dest_dir = self.type_to_dir.get(typecode)
        logger.debug("Type mapping lookup - typecode: %s -> dest_dir: %s",
                     typecode, dest_dir)

        if not dest_dir:
            # Fall back to ERR if available
            if 'ERR' in self.type_to_dir:
                dest_dir = self.type_to_dir['ERR']
                logger.warning("Unknown typecode: %s. Falling back to ERR: %s",
                               typecode, dest_dir)
                logger.debug("Using ERR fallback directory: %s", dest_dir)
            else:
                logger.error("Unknown typecode: %s and no ERR fallback available. "
                             "Available types: %s", typecode, list(self.type_to_dir.keys()))
                return False

        logger.debug("Checking if destination directory exists: %s", dest_dir)
        if not os.path.isdir(dest_dir):
            logger.error("Destination directory does not exist: %s (typecode: %s)",
                         dest_dir, typecode)
            return False

        logger.debug("Current working directory: %s", os.getcwd())
        try:
            os.chdir(dest_dir)
            logger.debug("Changed to destination directory: %s", dest_dir)
        except OSError as e:
            logger.error("Failed to change directory to %s: %s", dest_dir, e)
            return False

        # Check if lftp is installed
        lftp_path = shutil.which("lftp")
        logger.debug("LFTP path: %s", lftp_path)
        if not lftp_path:
            logger.error("lftp is not installed or not in PATH. Cannot perform transfer.")
            return False

        # Try as directory (mirror)
        mirror_cmd = [
            "lftp", "-u", self.config.creds, f"sftp://{self.config.host}/",
            "-e", f"{HOSTKEYFIX}; mirror -c  --parallel={self.config.threads} "
                  f"--use-pget-n={self.config.segments} \"{target}\" ;quit"
        ]
        logger.info("Running mirror command in %s: %s", dest_dir, ' '.join(mirror_cmd))
        logger.debug("Mirror command details - parallel: %d, segments: %d",
                     self.config.threads, self.config.segments)

        try:
            result = subprocess.run(mirror_cmd, capture_output=True, text=True, check=True) # nosec B603
            logger.debug("Mirror command completed successfully")

            if result.stdout:
                logger.debug("Mirror stdout: %s", result.stdout)
            if result.stderr:
                logger.debug("Mirror stderr: %s", result.stderr)

            transferred = True

        except subprocess.CalledProcessError as e:
            logger.debug("Mirror failed with return code %d", e.returncode)
            logger.debug("Mirror stderr: %s", e.stderr)
            logger.debug("Mirror stdout: %s", e.stdout)

            # Try as file (pget)
            pget_cmd = [
                "lftp", "-u", self.config.creds, f"sftp://{self.config.host}/",
                "-e", f"{HOSTKEYFIX}; pget -n {self.config.threads} \"{target}\" ;quit"
            ]
            logger.info("Mirror failed, trying pget command in %s: %s",
                        dest_dir, ' '.join(pget_cmd))
            logger.debug("Pget command details - threads: %d", self.config.threads)

            try:
                result = subprocess.run(pget_cmd, capture_output=True, text=True, check=True) # nosec
                logger.debug("Pget command completed successfully")

                if result.stdout:
                    logger.debug("Pget stdout: %s", result.stdout)
                if result.stderr:
                    logger.debug("Pget stderr: %s", result.stderr)

                transferred = True

            except subprocess.CalledProcessError as pget_error:
                logger.debug("Pget also failed with return code %d", pget_error.returncode)
                logger.debug("Pget stderr: %s", pget_error.stderr)
                logger.debug("Pget stdout: %s", pget_error.stdout)
                transferred = False

        # Set permissions on the transferred file/directory
        base = os.path.basename(target)
        logger.debug("Setting permissions on: %s", base)
        try:
            os.chmod(base, 0o666) # nosec
            logger.debug("Successfully set permissions 666 on %s", base)
        except OSError as e:
            logger.warning("Could not chmod %s: %s", base, e)

        if transferred:
            logger.info("Transfer of %s to %s completed successfully", target, dest_dir)
            logger.debug("Transfer success")
        else:
            logger.error("Transfer of %s to %s failed", target, dest_dir)

        logger.debug("Transfer function returning: %s", transferred)
        return transferred
