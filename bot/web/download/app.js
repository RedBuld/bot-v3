var tg = window.Telegram.WebApp;

tg.MainButton.setText("Скачать");
tg.MainButton.enable();
tg.MainButton.show();

var html_form = document.getElementById("download_config");
var base_url = window.location.origin + window.location.pathname;

Telegram.WebApp.onEvent('mainButtonClicked', function(){
   var formData = new FormData(html_form);
   var temp = {};
   var form = {
      'action': 'web_app_download',
      'link': payload['link'],
      'site': payload['site'],
      'user_id': payload['user_id'],
      'chat_id': payload['chat_id'],
      'message_id': payload['message_id'],
   };
   
   for(var pair of formData.entries())
   {
      temp[ pair[0] ] = pair[1];
   }

   if( 'start' in temp )
   {
      form['start'] = parseInt( temp['start'] );
   }

   if( 'end' in temp )
   {
      form['end'] = parseInt( temp['end'] );
   }

   if( 'format' in temp )
   {
      form['format'] = temp['format'];
   }

   if( 'auth' in temp )
   {
      form['auth'] = temp['auth'];
   }

   if( 'images' in temp )
   {
      form['images'] = true;
   }

   if( 'cover' in temp )
   {
      form['cover'] = true;
   }

   if( 'force_images' in payload)
   {
      form['images'] = true;
   }

   const xhr = new XMLHttpRequest();
   xhr.open("POST", payload['host'] + "download/setup");
   xhr.setRequestHeader("Content-Type", "application/json; charset=UTF-8");
   const body = JSON.stringify(form);
   xhr.onload = () => {
      if (xhr.readyState == 4 && xhr.status == 200) {
         console.log(JSON.parse(xhr.responseText));
         Telegram.WebApp.close();
      } else {
         alert(`Error: ${xhr.status}`);
      }
   };
   xhr.send(body);

   // Telegram.WebApp.sendData(JSON.stringify(form));
});