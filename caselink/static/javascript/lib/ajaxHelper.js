function alertAjax(url){
  $.ajax({
    'url':url,
    'cache': false
  }).done(function(data){
    alert(JSON.stringify(data));
  }).fail(function(){
    alert("Ajax Failure!");
  });
}

module.exports = alertAjax;
