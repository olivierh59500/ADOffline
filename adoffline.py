import time
import pprint
import tempfile
import sqlite3
import re
import sys
import os

# This function looks for "x: y" in an LDIF
# file and effectively splits them up using a regex
def match_param(line,param):
    var = None

    # These ones have two ::'s, presuambly to signify that
    # they are base64 encoded
    if param in ['objectSid','sIDHistory','objectGUID']:
        var = re.match('^'+param+'::\s([^$]+)\s*$', line.strip())
    else:
        # Everything else should be key: value, not key:: value
        var = re.match('^'+param+':\s([^$]+)\s*$', line.strip())

    if var != None:
        return var.group(1).strip()

    return None

# This updates the dict (if it doesn't already exist)
# with a name/value pair (and adds it to a list)
def update_struct(struct,name,val):
    if val==None:
        return False

    if not name in struct:
        struct[name] = []
    struct[name].append(val)
    return True

# This function processes the completed struct. For example,
# we have just seen a new 'dn' and therefore must have finished 
# the last block
def process_struct(struct,sql):

    # If there isn't a DN in there, we aren't interested
    if not 'dn' in struct or not 'objectClass' in struct: 
        return

    if 'user' in struct['objectClass'] or 'group' in struct['objectClass']:
        insert_into_db(struct,sql)

    return

# Build the SQL database schema
def build_db_schema(sql):
    
    c = sql.cursor()

    # Create the tables
    c.execute('''CREATE TABLE raw_users
                 ('objectClass','dn','title', 'cn','sn','description','instanceType','displayName','name','dNSHostName','userAccountControl','badPwdCount','primaryGroupID','adminCount','objectSid','sid','rid','sAMAccountName','sAMAccountType',
                 'objectCategory','operatingSystem','operatingSystemServicePack','operatingSystemVersion','managedBy','givenName','info','department','company','homeDirectory','userPrincipalName',
                 'manager','mail','groupType')''') 
    c.execute("CREATE TABLE raw_memberof ('dn_group','dn_member')")

    sql.commit()
    return
 
# Add indexes to the schema
def fix_db_indices(sql):
    
    c = sql.cursor()

    # Create the indicies
    c.execute("CREATE UNIQUE INDEX raw_users_dn on raw_users (dn)")
    c.execute("CREATE INDEX raw_users_dnshostname on raw_users (objectClass,dNSHostName)")
    c.execute("CREATE INDEX raw_users_samaccountname on raw_users (objectClass,sAMAccountName)")
    c.execute("CREATE INDEX raw_memberof_group_user on raw_memberof('dn_group','dn_member')")
    c.execute("CREATE INDEX raw_memberof_user_group on raw_memberof('dn_member','dn_group')")

    sql.commit()
    return

# Create the database views (bitwise expansion etc)
def create_views(sql):
    
    c = sql.cursor()

    # Generate the main view with calculated fields
    c.execute('''CREATE VIEW view_raw_users AS select objectClass, dn, title, cn, sn, description, instanceType, displayName, name, dNSHostName, userAccountControl, badPwdCount, primaryGroupID, adminCount, objectSid, sid, rid, sAMAccountName, sAMAccountType, objectCategory, managedBy, givenName, info, department, company, homeDirectory, userPrincipalName, manager, mail, operatingSystem, operatingSystemVersion, operatingSystemServicePack, groupType,
     (CASE (userAccountControl&0x00000001) WHEN (0x00000001) THEN 1 ELSE 0 END) AS ADS_UF_SCRIPT,
     (CASE (userAccountControl&0x00000002) WHEN (0x00000002) THEN 1 ELSE 0 END) AS ADS_UF_ACCOUNTDISABLE,
	 (CASE (userAccountControl&0x00000008) WHEN (0x00000008) THEN 1 ELSE 0 END) AS ADS_UF_HOMEDIR_REQUIRED,
	 (CASE (userAccountControl&0x00000010) WHEN (0x00000010) THEN 1 ELSE 0 END) AS ADS_UF_LOCKOUT,
	 (CASE (userAccountControl&0x00000020) WHEN (0x00000020) THEN 1 ELSE 0 END) AS ADS_UF_PASSWD_NOTREQD,
	 (CASE (userAccountControl&0x00000040) WHEN (0x00000040) THEN 1 ELSE 0 END) AS ADS_UF_PASSWD_CANT_CHANGE,
	 (CASE (userAccountControl&0x00000080) WHEN (0x00000080) THEN 1 ELSE 0 END) AS ADS_UF_ENCRYPTED_TEXT_PASSWORD_ALLOWED,
	 (CASE (userAccountControl&0x00000100) WHEN (0x00000100) THEN 1 ELSE 0 END) AS ADS_UF_TEMP_DUPLICATE_ACCOUNT,
	 (CASE (userAccountControl&0x00000200) WHEN (0x00000200) THEN 1 ELSE 0 END) AS ADS_UF_NORMAL_ACCOUNT,
	 (CASE (userAccountControl&0x00000800) WHEN (0x00000800) THEN 1 ELSE 0 END) AS ADS_UF_INTERDOMAIN_TRUST_ACCOUNT,
	 (CASE (userAccountControl&0x00001000) WHEN (0x00001000) THEN 1 ELSE 0 END) AS ADS_UF_WORKSTATION_TRUST_ACCOUNT,
	 (CASE (userAccountControl&0x00002000) WHEN (0x00002000) THEN 1 ELSE 0 END) AS ADS_UF_SERVER_TRUST_ACCOUNT,
	 (CASE (userAccountControl&0x00010000) WHEN (0x00010000) THEN 1 ELSE 0 END) AS ADS_UF_DONT_EXPIRE_PASSWD,
	 (CASE (userAccountControl&0x00020000) WHEN (0x00020000) THEN 1 ELSE 0 END) AS ADS_UF_MNS_LOGON_ACCOUNT,
	 (CASE (userAccountControl&0x00040000) WHEN (0x00040000) THEN 1 ELSE 0 END) AS ADS_UF_SMARTCARD_REQUIRED,
	 (CASE (userAccountControl&0x00080000) WHEN (0x00080000) THEN 1 ELSE 0 END) AS ADS_UF_TRUSTED_FOR_DELEGATION,
	 (CASE (userAccountControl&0x00100000) WHEN (0x00100000) THEN 1 ELSE 0 END) AS ADS_UF_NOT_DELEGATED,
	 (CASE (userAccountControl&0x00200000) WHEN (0x00200000) THEN 1 ELSE 0 END) AS ADS_UF_USE_DES_KEY_ONLY,
	 (CASE (userAccountControl&0x00400000) WHEN (0x00400000) THEN 1 ELSE 0 END) AS ADS_UF_DONT_REQUIRE_PREAUTH,
	 (CASE (userAccountControl&0x00800000) WHEN (0x00800000) THEN 1 ELSE 0 END) AS ADS_UF_PASSWORD_EXPIRED,
	 (CASE (userAccountControl&0x01000000) WHEN (0x01000000) THEN 1 ELSE 0 END) AS ADS_UF_TRUSTED_TO_AUTHENTICATE_FOR_DELEGATION,
	 CASE WHEN (sAMAccountType==0) THEN 1 ELSE 0 END AS SAM_DOMAIN_OBJECT,
	 CASE WHEN (sAMAccountType==0x10000000) THEN 1 ELSE 0 END AS SAM_GROUP_OBJECT,
	 CASE WHEN (sAMAccountType==0x10000001) THEN 1 ELSE 0 END AS SAM_NON_SECURITY_GROUP_OBJECT,
	 CASE WHEN (sAMAccountType==0x20000000) THEN 1 ELSE 0 END AS SAM_ALIAS_OBJECT,
	 CASE WHEN (sAMAccountType==0x20000001) THEN 1 ELSE 0 END AS SAM_NON_SECURITY_ALIAS_OBJECT,
	 CASE WHEN (sAMAccountType==0x30000000) THEN 1 ELSE 0 END AS SAM_NORMAL_USER_ACCOUNT,
	 CASE WHEN (sAMAccountType==0x30000001) THEN 1 ELSE 0 END AS SAM_MACHINE_ACCOUNT,
	 CASE WHEN (sAMAccountType==0x30000002) THEN 1 ELSE 0 END AS SAM_TRUST_ACCOUNT,
	 CASE WHEN (sAMAccountType==0x40000000) THEN 1 ELSE 0 END AS SAM_APP_BASIC_GROUP,
	 CASE WHEN (sAMAccountType==0x40000001) THEN 1 ELSE 0 END AS SAM_APP_QUERY_GROUP,
	 CASE WHEN (sAMAccountType==0x7fffffff) THEN 1 ELSE 0 END AS SAM_ACCOUNT_TYPE_MAX FROM raw_users''')

    # Add additional fields to the group one
    c.execute('''CREATE VIEW view_groups AS select view_raw_users.*,
     (CASE (groupType&0x00000001) WHEN (0x00000001) THEN 1 ELSE 0 END) AS GROUP_CREATED_BY_SYSTEM,
     (CASE (groupType&0x00000002) WHEN (0x00000002) THEN 1 ELSE 0 END) AS GROUP_SCOPE_GLOBAL,
     (CASE (groupType&0x00000004) WHEN (0x00000004) THEN 1 ELSE 0 END) AS GROUP_SCOPE_LOCAL,
     (CASE (groupType&0x00000008) WHEN (0x00000008) THEN 1 ELSE 0 END) AS GROUP_SCOPE_UNIVERSAL,
     (CASE (groupType&0x00000010) WHEN (0x00000010) THEN 1 ELSE 0 END) AS GROUP_SAM_APP_BASIC,
     (CASE (groupType&0x00000020) WHEN (0x00000020) THEN 1 ELSE 0 END) AS GROUP_SAM_APP_QUERY,
     (CASE (groupType&0x80000000) WHEN (0x80000000) THEN 1 ELSE 0 END) AS GROUP_SECURITY,
     (CASE (groupType&0x80000000) WHEN (0x80000000) THEN 0 ELSE 1 END) AS GROUP_DISTRIBUTION FROM view_raw_users WHERE objectClass = 'group' ''')

    # Create the user and computer views. In effect it is the same table though.
    c.execute("CREATE VIEW view_users AS select view_raw_users.* FROM view_raw_users WHERE objectClass = 'user'")
    c.execute("CREATE VIEW view_computers AS select view_raw_users.* FROM view_raw_users WHERE objectClass = 'computer'")

    sql.commit()
    return

# Insert the new user/group/computer into the database
def insert_into_db(struct,sql):
    c = sql.cursor()
    ldap_single_params = ['title','cn','sn','description','instanceType','displayName','name','dNSHostName','userAccountControl','badPwdCount','primaryGroupID','adminCount','objectSid','sAMAccountName','sAMAccountType','objectCategory','operatingSystem','operatingSystemServicePack','operatingSystemVersion','managedBy','givenName','info','department','company','homeDirectory','userPrincipalName','manager','mail','groupType']
    ldap_values = []
    for ind in ldap_single_params:
        ldap_values.append(safe_struct_get(struct,ind))

    # Raw_users contains everything
    sql_statement = "insert into raw_users ('objectClass','dn','title','cn','sn','description','instanceType','displayName','name','dNSHostName','userAccountControl','badPwdCount','primaryGroupID','adminCount','objectSid','sAMAccountName','sAMAccountType','objectCategory','operatingSystem','operatingSystemServicePack','operatingSystemVersion','managedBy','givenName','info','department','company','homeDirectory','userPrincipalName','manager','mail','groupType') VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
    ldap_values.insert(0,struct['dn'])

    # Make sure that this is a user, group or computer
    oc = None
    if 'computer' in struct['objectClass']:
        oc = 'computer'
    elif 'group' in struct['objectClass']:
        oc = 'group'
    elif 'user' in struct['objectClass']:
        oc = 'user'
    else:
        return

    ldap_values.insert(0,oc)
    c.execute(sql_statement, ldap_values)

    if 'memberOf' in struct:
        for m in struct['memberOf']:
            sql_memberof = 'replace into raw_memberof (dn_group,dn_member) VALUES (?,?)'
            c.execute(sql_memberof, [m,struct['dn']])

    if 'member' in struct and oc == 'group':
        for m in struct['member']:
            sql_member = 'replace into raw_memberof (dn_group,dn_member) VALUES (?,?)'
            c.execute(sql_member, [struct['dn'],m])

    sql.commit()
    return

# Get the specific value from the dict name/value pair
def safe_struct_get(struct,name):
    if not struct:
        return None
    
    if not name in struct:
        return None

    if not struct[name][0]:
        return None

    if name in ['instanceType','userAccountControl','badPwdCount','primaryGroupID','adminCount','sAMAccountType','groupType']:
        val = int(struct[name][0])
        if not val:
            return int(0)
        else:
            return val

    return struct[name][0]

# Write a log entry to stdout
def log(strval):
    sys.stdout.write('['+time.strftime("%d/%b/%y %H:%M:%S")+'] '+strval)
    sys.stdout.flush()
    return

# Write a log entry to stderr
def err(strval):
    sys.stderr.write('['+time.strftime("%d/%b/%y %H:%M:%S")+'] '+strval)
    sys.stderr.flush()
    return

# Create the SQLite3 database
sys.stdout.write("AD LDAP to SQLite Offline Parser\nStuart Morgan (@ukstufus) <stuart.morgan@mwrinfosecurity.com>\n\n")

if len(sys.argv)<2:
    err("Specify the source LDIF filename on the command line. Create it with a command such as:\n")
    err("ldapsearch -h <ip> -x -D <username> -w <password> -b <base DN> -E pr=1000/noprompt -o ldif-wrap=no \"(|(objectClass=group)(objectClass=user))\" > ldap.output\n")
    sys.exit(1)

source_filename = sys.argv[1]
if not os.path.isfile(source_filename):
    err("Unable to read "+source_filename+". Make sure this is a valid file.\n")
    sys.exit(2)


log("Creating database: ")
db_file = tempfile.NamedTemporaryFile(delete=False)
db_filename = db_file.name+'.'+time.strftime('%Y%m%d%H%M%S')+'.ad-ldap.db'
db_file.close()
sql = sqlite3.connect(db_filename)
build_db_schema(sql)
create_views(sql)
sys.stdout.write(db_filename+"\n")

f = open(source_filename,"r")
log("Reading LDIF..")
# Open the LDAP file and read its contents
lines = f.readlines()
sys.stdout.write(".done\n")
f.close()

# Create an initial object
current_dn = {}

# The list of ldap parameters to save
ldap_params = ['objectClass','title','cn','sn','description','instanceType','displayName','member','memberOf','name','dNSHostName','userAccountControl','badPwdCount','primaryGroupID','adminCount','objectSid','sAMAccountName','sAMAccountType','objectCategory','operatingSystem','operatingSystemServicePack','operatingSystemVersion','managedBy','givenName','info','department','company','homeDirectory','sIDHistory','userPrincipalName','manager','mail','groupType']

log("Parsing LDIF.")
# Go through each line in the LDIF file
for line in lines:

    # If it starts with DN, its a new "block"
    val = match_param(line,'dn')
    if val != None: 
        process_struct(current_dn,sql)
        current_dn = {}
        current_dn['dn'] = val
        continue

    for p in ldap_params:
        update_struct(current_dn, p, match_param(line,p))
    
# We are at the last line, so process what
# is left as a new block
process_struct(current_dn,sql)
sys.stdout.write(".done\n")

log("Applying indices..")
fix_db_indices(sql)
sys.stdout.write(".done\n")

sql.close()
log("Completed")
