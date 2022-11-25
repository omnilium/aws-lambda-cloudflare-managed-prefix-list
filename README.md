# AWS Lambda Cloudflare Managed Prefix List

An AWS Lambda function that automatically updates and manages a managed prefix list with Cloudflare's IPs for use in EC2 security groups.

## How to use

1. Create a new role for the lambda function

   Create a new service role for the lambda function to use. Example permissions JSON:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "SID1",
         "Effect": "Allow",
         "Action": [
           "ec2:GetManagedPrefixListEntries",
           "ec2:ModifyManagedPrefixList",
           "logs:PutLogEvents"
         ],
         "Resource": [
           "arn:aws:logs:eu-central-1:<ACCOUNT_ID>:log-group:*:log-stream:*",
           "arn:aws:ec2:*:<ACCOUNT_ID>:prefix-list/*"
         ]
       },
       {
         "Sid": "SID2",
         "Effect": "Allow",
         "Action": "ec2:DescribeManagedPrefixLists",
         "Resource": "*"
       },
       {
         "Sid": "SID3",
         "Effect": "Allow",
         "Action": ["logs:CreateLogStream", "logs:CreateLogGroup"],
         "Resource": "arn:aws:logs:eu-central-1:<ACCOUNT_ID>:log-group:*"
       }
     ]
   }
   ```

2. Create a new lambda function

   Create a new lambda function using the code in `lambda_function.py`, with `Python3.8` as the runtime and with the role created at step 1.

3. Set the function's timeout to 30 seconds

   Under `Configuration`, `General Configuration`, click `Edit` and set the `Timeout` value to `0 min 30 sec`.

   This is important because the call to update the managed prefix list can take a long time, and AWS' default of 3 seconds is not enough.

4. Add the required environment variables

   Under `Configuration`, `Environment variables`, add the following environment variables:

   ```
   DEBUG: False
   DRY_RUN: False
   ```

   Setting `DEBUG` to `True` will output debug information to the logs, whilst setting `DRY_RUN` to `True` will prevent the boto3 client from making changes, only checking for permissions.

5. Add an EventBridge trigger to automatically run the function periodically

   Click `Add trigger`, chose `EventBridge (CloudWatch Events)`, `Create a new rule`, give it an intuitive name, `Schedule expression`, then in the field input `rate(7 days)`.

   This will automatically run the function every 7 days. Feel free to adjust this interval to your liking.

6. Create the managed prefix list.

   Under `VPC`, `Managed prefix lists`, click on `Create prefix list`. Give it an intuitive name such as `com.cloudflare.global.proxy_ips`, set the max entries to `20`, leave the address family as `IPv4` (IPv6 currently not supported by this script), then in tags add the tags listed in the script. By default, these are:

   ```
   AutoUpdate: True
   Updater: Cloudflare
   ```

7. Optionally, run the function by testing it for the list to update, or wait for the first automatic trigger.

### License

The code within this repo is licensed under the GNU GPLv3 license.
