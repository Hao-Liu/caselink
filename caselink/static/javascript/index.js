var taskPanelPolling = false;
var htmlify = require('./lib/htmlify.js');
var Vue = require('vue');
var _ = require('lodash');

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

var taskData =  {
  tasks: [],
  backups: [],
  results: []
};
var vm = new Vue({
  el: "#caselink",
  data: {
  },
  components: {
    'task-panel': {
      data: function (){
        return taskData;
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
        myHtmlify: function(value){
          return htmlify(value);
        },
      },
    },
    'pattern-matcher': {
      data: function (){
        return {
          pattern: '',
          cases: ''
        };
      },
      methods: {
        fetchCases: _.debounce(function(pattern){
          var that = this;
          $.get('pattern-matcher/' + this.pattern)
            .done(function(data){
              that.cases = data.cases.join("<br>");
            });
        },
          800),
      },
      watch: {
        pattern: function(){
          this.fetchCases(this.pattern);
        }
      },
    },
  },
  watch: {
  },
  delimiters: ['${', '}'],
});

$(document).ready(function() {
  "use strict";

  $('#task-panel').on('hidden.bs.modal', function (e) {
    taskPanelPolling = false;
  });

  $('#task-panel').on('show.bs.modal', function (e) {
    taskPanelPolling = true;
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
        taskData.tasks = data.tasks;
        taskData.backups = data.backups;
        taskData.results = data.results;
      })
      .always(function(){
        if(taskPanelPolling)
          setTimeout(poll_status, 1000);
      });
  }
});
