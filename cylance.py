import argparse, sys, os, logging
from antivirus.cylance import cylance
from os.path import basename
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import smtplib
import configparser

# @type: html or plain
def send_mail(send_from, send_to, subject, text, files=None, type="html", server="", smtp_auth = True, smtp_user="", smtp_pass = ""):
    COMMASPACE = ', '
    assert isinstance(send_to, list)
    msg = MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)
    msg['Subject'] = subject
    msg.attach(MIMEText(text, type))

    for f in files or []:
        with open(f, "rb") as fil:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(fil.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', "attachment; filename= %s" % basename(f))
            msg.attach(part)
    try:
        smtp = smtplib.SMTP()
        smtp.connect(server)
        smtp.starttls()
        if (smtp_auth):
            smtp.login(smtp_user, smtp_pass)

        smtp.sendmail(send_from, send_to, msg.as_string())
        smtp.quit()
    except:
        type, value, traceback = sys.exc_info()
        print("Could not send an email!")
        print(type)
        print(value)

def main():
    if getattr(sys, 'frozen', False):
        current_dir = os.path.dirname(sys.executable)
    else:
        current_dir = os.path.dirname(os.path.realpath(__file__))

    parser = argparse.ArgumentParser(description='Remove computers from the Cylance web console')
    parser.add_argument('--host', required=False, help='Cylance host (i.e. https://protectapi-{region-code}.cylance.com)', default="")
    parser.add_argument('--appid', required=False, help='Cylance application id', default="")
    parser.add_argument('--tenantid', required=False, help='Cylance tenant id', default="")
    parser.add_argument('--appsecret', required=False, help='Cylance application secret', default="")
    parser.add_argument('--config', required=False, help='Configuration file with Cylance host, appid, tenantid and application secret', default="")
    parser.add_argument('--system', required=False, help='Name of system that needs to be removed', default="")
    parser.add_argument('--smtpauth', required=False, action="store_true", default=False, help='Use SMTP authentication for sending alerts')
    parser.add_argument('--smtpuser', required=False, help='SMTP user for authentication', default="")
    parser.add_argument('--smtppass', required=False, help='SMTP password for authentication', default="")
    parser.add_argument('--smtphost', required=False, help='SMTP server host name or ip', default="")
    parser.add_argument('--fromuser', required=False, help='Email address that sends the alert email', default="")
    parser.add_argument('--touser', required=False, help='Email address that receives the alert email', default="")
    parser.add_argument('--stripdollar', required=False, action='store_true', default=False, help='Remove a $ character at the end of the system')
    parser.add_argument('--debug', required=False, action='store_true', default=False, help='Enable debugging -> creates a log file')
    parser.add_argument('--logfile', required=False, help='Log file location', default=os.path.dirname(current_dir) + "/debug.log")
    # show help when no arguments are given
    if len(sys.argv) == 1:
        parser.print_help(sys.stdout)
        sys.exit(0)

    args = parser.parse_args()
    config_file = args.config
    system_host_name = args.system.upper()

    if config_file == "":
        host = args.host
        app_id = args.appid
        tenant_id = args.tenantid
        app_secret = args.appsecret
        smtp_auth = args.smtpauth
        smtp_host = args.smtphost
        smtp_user = args.smtpuser
        smtp_pass = args.smtppass
        from_user = args.fromuser
        to_user = args.touser
        strip_dollar = args.stripdollar
        debug = args.debug
        log_file = args.logfile
    else:
        try:
            f = open(config_file, "r")
            content = f.read()
            config = configparser.ConfigParser()
            config.read_string(content)
            host = config['cylance'].get('host', '')
            app_id = config['cylance'].get('appid', '')
            tenant_id = config['cylance'].get('tenantid', '')
            app_secret = config['cylance'].get('appsecret', '')
            smtp_auth = config['smtp'].getboolean('smtpauth', False)
            smtp_host = config['smtp'].get('smtphost', '')
            smtp_user = config['smtp'].get('smtpuser', '')
            smtp_pass = config['smtp'].get('smtppass', '')
            from_user = config['smtp'].get('fromuser', '')
            to_user = config['smtp'].get('touser', '')
            strip_dollar = config['general'].getboolean('stripdollar', False)
            debug = config['general'].getboolean('debug', False)
            log_file = config['general'].get('logfile', os.path.dirname(current_dir + "/debug.log"))
        except:
            print("Could not open configuration file " + config_file)
            exit(0)
    if debug:
        logging.basicConfig(filename=log_file, level=logging.DEBUG)
        logging.debug("Show all cli arguments")
        logging.debug(sys.argv)

    if strip_dollar and system_host_name.endswith('$'):
        logging.debug("Stripping $ at the end if there is any")
        system_host_name = system_host_name[:-1]
        logging.debug("System name " + system_host_name)

    logging.debug("Fetching systems from Cylance api...")
    c = cylance(host, app_id, tenant_id, app_secret)
    systems = c.get_all_devices()
    id_list = []
    for system in systems:
        id = system.get('id', '')
        name = system.get('name', '').upper()
        if name == system_host_name:
            id_list.append(id)
    logging.debug("Amount of systems returned: " + str(len(id_list)))
    if len(id_list) == 1:
        res = c.delete_device(id_list[0])
        if not res:
            subject = "Could not automatically delete computer " + system_host_name + " from Cylance!"
            message = "When trying to delete computer " + system_host_name + " from the Cylance console, I've encountered an unknown error!<br/>"
            message = message + "Please check manually in the Cylance console if this system has been deleted."
            logging.debug("Could not delete computer!")
            logging.debug(message)
            send_mail(from_user, [to_user], subject, message, server=smtp_host, smtp_auth=smtp_auth, smtp_user=smtp_user, smtp_pass=smtp_pass)
    else:
        subject = "TEST - IGNORE - Multiple instances of computer " + system_host_name + " have been found in Cylance!"
        message = "When trying to delete computer " + system_host_name + " from the Cylance console, I've detected that there are " + str(len(id_list)) + " systems with the same hostname!<br/>"
        message = message + "Please delete manually from the Cylance console."
        logging.debug("Could not delete computer!")
        logging.debug(message)
        send_mail(from_user, [to_user], subject, message, server=smtp_host, smtp_auth=smtp_auth, smtp_user=smtp_user, smtp_pass=smtp_pass)

if __name__ == "__main__":
    debug = False
    log_file = ""
    main()
