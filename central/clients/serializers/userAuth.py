from rest_framework import serializers
from clients.models import User
from logic import auth, emailHelper
from django.core.exceptions import ValidationError as DjangoValidationError
from logic.exceptions import PermissionDenied


class AuthenticateCredentialsSerializer(serializers.Serializer):    
    email = serializers.CharField(required=True, label="Email", max_length=250)
    password = serializers.CharField(required=True, label="Password", max_length=250)    


class AuthenticateTokenSerializer(serializers.Serializer):    
    token = serializers.CharField(required=True, label="Token", max_length=2048)


class PasswordChangeSerializer(serializers.Serializer):
    '''
        Requires current user on context
    '''
    
    oldPassword = serializers.CharField(required=True, label="Old Password", max_length=250)
    newPassword = serializers.CharField(required=True, label="New Password", max_length=250)

    def validate(self, data):
        
        user = self.context['user']
        
        #validate old password
        if not auth.checkUserPassword(user,data['oldPassword']):
            raise serializers.ValidationError({'oldPassword':"Old password is invalid"})

        #Validate password
        try:
            auth.validateUserPassword(user, data['newPassword'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'newPassword':e.messages})

        if data['oldPassword'] == data['newPassword']:
            raise serializers.ValidationError({'newPassword':"New password must be different from old password."})

        
        auth.setUserPassword(user,data['newPassword'])     
        
        self.instance = user

        return data

    def save(self):  
        self.instance.save()
        return self.instance
    

class RequestPasswordRecoverySerializer(serializers.Serializer):
   
    email = serializers.EmailField(required=True, label="Email", max_length=250)

    def validate(self, data):
        
        user = None
        
        #Try to get user by email. If not found fail silently, 
        #This way we reduce user email enumerations
        try:
            user = User.objects.get(email=data['email']) 
        except User.DoesNotExist:
            pass
        
        self.instance = user

        return data


    def save(self):  

        if not self.instance:
            return

        #Create token
        token = auth.createUserPasswordRecoveryToken(self.instance)

        emailText = auth.PASSWORD_RECOVERY_EMAIL_TEXT.format(token)
        emailHtml = auth.PASSWORD_RECOVERY_EMAIL_TEXT_HTML.format(token)
        
        emailHelper.sendEmail(
            "Password Recovery",
            [self.instance.email], 
            fromEmail=None, 
            plainText = emailText, 
            htmlText=emailHtml, 
            async=True
        )



class PasswordChangeSerializer(serializers.Serializer):
    '''
        Requires current user on context
    '''
    
    oldPassword = serializers.CharField(required=True, label="Old Password", max_length=250)
    newPassword = serializers.CharField(required=True, label="New Password", max_length=250)

    def validate(self, data):
        
        user = self.context['user']
        
        #validate old password
        if not auth.checkUserPassword(user,data['oldPassword']):
            raise serializers.ValidationError({'oldPassword':"Old password is invalid"})

        #Validate password
        try:
            auth.validateUserPassword(user, data['newPassword'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'newPassword':e.messages})

        if data['oldPassword'] == data['newPassword']:
            raise serializers.ValidationError({'newPassword':"New password must be different from old password."})

        
        auth.setUserPassword(user,data['newPassword'])     
        
        self.instance = user

        return data


    def save(self):  
        self.instance.save()
        return self.instance
        

class TokenPasswordChangeSerializer(serializers.Serializer):
    
    token = serializers.CharField(required=True, label="Token", max_length=2048)
    password = serializers.CharField(required=True, label="Password", max_length=250)

    def validate(self, data):
        
        user = auth.validateUserPasswordRecoveryToken(data['token'])

        try:
            auth.validateUserPassword(user, data['password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'password':e.messages})

        user.requiresPasswordChange = False
        user.requiresPasswordChangeMsg = ""
        auth.setUserPassword(user,data['password'])     
        self.instance = user

        return data


    def save(self):  

       self.instance.save()
       return self.instance