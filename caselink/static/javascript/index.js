var polling = false;
var htmlify = require('./lib/htmlify.js');
$(document).ready(function() {
  "use strict";
  var task_progress = $("#task_progress");
  var progress_bar = $("#task_progress .progress-bar-proto").detach();
  var empty_task = $("#task_progress .empty-proto");

  var backup_list = $("#backup_list ul.list-group");
  var backup_item = $("#backup_list li.backup-item").detach();
  var empty_backup = $("#backup_list li.empty-item");

  var result_list = $("#result_list ul.list-group");
  var result_item = $("#result_list li.result-item").detach();
  var empty_result = $("#result_list li.empty-item");

  $('#task_panel').on('hidden.bs.modal', function (e) {
    polling = false;
  });

  $('#task_panel').on('show.bs.modal', function (e) {
    polling = true;
    poll_status();
  });

  function gen_progress_bar(cur, total, text){
    let bar = progress_bar.clone();
    let progress = bar.find(".progress-bar");
    let percent = (cur/total) * 100.0;

    if(text){
      progress.text(text);
    }
    else{
      progress.text("" + cur + "/" + total + "");
    }
    progress
      .attr("aria-valuenow", cur)
      .attr("aria-valuemax", total)
      .attr("aria-valuemin", 0)
      .css("min-width", "6em")
      .css("width", "" + percent + "%");

    return bar;
  }

  function ajax_with_alert(url){
    $.ajax({
      'url':url,
      'cache': false
    }).done(function(data){
      alert(JSON.stringify(data));
    });
  }

  $(".btn-cancel").click(function(){ ajax_with_alert('control/trigger/?cancel=true'); });
  $(".btn-auto-error").click(function(){ ajax_with_alert('control/trigger/?async=true&trigger=autocase_error_check'); });
  $(".btn-manual-error").click(function(){ ajax_with_alert('control/trigger/?async=true&trigger=manualcase_error_check'); });
  $(".btn-linkage-error").click(function(){ ajax_with_alert('control/trigger/?async=true&trigger=linkage_error_check'); });
  $(".btn-sync-polarion").click(function(){ ajax_with_alert('control/trigger/?async=true&trigger=polarion_sync'); });
  $(".backup-new").click(function(){ ajax_with_alert('control/trigger/?async=true&trigger=dump_all_db'); });
  $(".backup-upload").click(function(){
    $('#backup_upload_input').click();
  });
  $('#backup_upload_input').change(function() {
    console.log("changed");
    $('#backup_upload_form').submit();
  });
  $("#backup_list .list-group").on('click', '.backup-download', function(){
    let yaml = $(this).closest('li').clone().children().remove().end().text().trim();
    top.location.href = 'control/backup/' + yaml;
    console.log( 'control/backup/' + yaml);
  });
  $("#backup_list .list-group").on('click', '.backup-restore', function(){
    let yaml = $(this).closest('li').clone().children().remove().end().text().trim();
    ajax_with_alert('control/restore/'+ yaml);
  });
  $("#backup_list .list-group").on('click', '.backup-delete', function(){
    let yaml = $(this).closest('li').clone().children().remove().end().text().trim();
    ajax_with_alert('control/backup/'+ yaml + '?delete=true');
  });

  function poll_status(){
    $.ajax({
      'url':'control/',
      'cache': false
    })
    .done(function(data){
      task_progress.empty();
      if($.isEmptyObject(data.task)) {
        task_progress.append(empty_task);
      }
      else{
        for(let i in data.task){
          console.log(data.task);
          console.log(data.task[i]);
          task_progress.append("<h3>"+i+"</h3>");
          if(data.task[i].meta){
            let cur = data.task[i].meta.current;
            let total = data.task[i].meta.total;
            task_progress.append(gen_progress_bar(cur,total));
          }
          else{
            task_progress.append(gen_progress_bar(1, 1, data.task[i].state || "STATE NOT AVALIABLE"));
          }
        }
      }

      backup_list.empty();
      if($.isEmptyObject(data.backup)) {
        backup_list.append(empty_backup);
      }
      else{
        for(let i = 0, len = data.backup.length; i < len; i++){
          let item = backup_item.clone();
          item.prepend("<span class=\"label label-default\">"+ (parseInt(data.backup[i].size)/(1024*1024)).toFixed(1) +"MB</span>");
          item.prepend(data.backup[i].file);
          backup_list.append(item);
        }
      }

      result_list.empty();
      if($.isEmptyObject(data.results)) {
        backup_list.append(empty_backup);
      }
      else{
        for(var i = 0, len = data.results.length; i < len; i++){
          let item = result_item.clone();
          item.prepend("<h3>"+ data.results[i].task_id +"</h3>");
          item.find(".well").html(htmlify(data.results[i].result));
          result_list.append(item);
        }
      }
    });
    if(polling)
      setTimeout(poll_status, 1000);
  }
});
