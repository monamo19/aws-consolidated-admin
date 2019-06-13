 security.yaml is applied to the top level org account 
 and users.yaml defines all of the IAM users and needs to be applied to the top level account first 
So first you apply all three templates to the top level account
Then you apply baseline.yml to every account in your organization (Child+ Master)
 
 security.yaml creates below:
 
 	IAM Group for All Users 	
	IAM Group for Billing Users 
 	IAM Group for ReadOnly Users
	IAM Group for PowerUsers 	
	IAM Group for AdministratorsGroup 
 
 Users. yaml creal below
 Creates following Groups:
and below users:

