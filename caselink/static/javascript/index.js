var polling = false;
var htmlify = require('./lib/htmlify.js');
var Vue = require('vue');

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

var vm = new Vue({
  el: "#task-panel",
  data: {
    tasks: [],
    backups: [],
    results: []
  },
  methods: {
    triggerTask: function(taskParams) {
      alertAjax('control/trigger/' + taskParams);
    },
    backupRestore: function(fileName) {
      alertAjax('control/restore/'+ fileName);
    },
    backupDelete: function(fileName) {
      alertAjax('control/backup/'+ fileName + '?delete=true');
    },
    backupNew: function() {
      this.triggerTask('?async=true&trigger=dump_all_db');
    },
    backupUpload: function() {
      $('#backup-upload-input').click();
    },
  },
  filters: {
    myHtmlify: function(value){
      return htmlify(value);
    },
  },
  delimiters: ['${', '}']
});

$(document).ready(function() {
  "use strict";

  $('#task-panel').on('hidden.bs.modal', function (e) {
    polling = false;
  });

  $('#task-panel').on('show.bs.modal', function (e) {
    polling = true;
    poll_status();
  });

  $(".backup-upload").click(function(){
    $('#backup-upload-input').click();
  });
  $('#backup-upload-input').change(function() {
    $('#backup-upload-form').submit();
  });

  function poll_status(){
    $.ajax({
      'url':'control/',
      'cache': false
    })
      .done(function(data){
        vm.tasks = data.tasks;
        vm.backups = data.backups;
        vm.results = data.results;
      })
      .always(function(){
        if(polling)
          setTimeout(poll_status, 1000);
      });
  }
});
