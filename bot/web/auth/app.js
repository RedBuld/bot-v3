var tg = window.Telegram.WebApp;

tg.MainButton.setText("Авторизоваться");
tg.MainButton.disable();
tg.MainButton.hide();

var html_form = document.getElementById("auth_config");
var base_url = window.location.origin + window.location.pathname;

var login_input = document.getElementById("login");
var password_input = document.getElementById("password");

login_input.addEventListener('change',function()
{
   maybe_allow_send();
})
password_input.addEventListener('change',function()
{
   maybe_allow_send();
})

function maybe_allow_send()
{
   if(login_input.value != '' && password_input.value != '')
   {
      tg.MainButton.enable();
      tg.MainButton.show();
   }
   else
   {
      tg.MainButton.disable();
      tg.MainButton.hide();
   }
}

Telegram.WebApp.onEvent('mainButtonClicked', function(){
   var formData = new FormData(html_form);
   var temp = {};
   var form = {
      'action': 'web_app_auth',
      'site': payload['site'],
   };
   
   for(var pair of formData.entries())
   {
      temp[ pair[0] ] = pair[1];
   }

   Telegram.WebApp.sendData(JSON.stringify(form));
});