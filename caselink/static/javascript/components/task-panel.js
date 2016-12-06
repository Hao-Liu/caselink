var alertAjax = require('../lib/ajaxHelper.js');
var htmlify = require('../lib/htmlify.js');

var taskData =  {
  tasks: [],
  backups: [],
  results: [],
};

module.exports = {
  taskData: taskData,
  props: ['polling'],
  template: "#task-panel",
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
      this.$el.querySelector("#backup-upload-input").click();
    },
    myHtmlify: function(value){
      return htmlify(value);
    },
    pollStatus: function(){
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
          if(this.polling)
            setTimeout(pollStatus, 1000);
        });
    },
  },
  mounted: function(){
    var that = this;
    this.$el.querySelector("#backup-upload-input").addEventListener('change', function(){
      that.$el.querySelector("#backup-upload-form").submit();
    });
  },
  watch: {
    polling: function(value){
      if(this.polling){
        this.pollStatus();
      }
    }
  },
  delimiters: ['${', '}'],
};
