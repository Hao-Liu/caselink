require("./lib/datatables-templates.js");
var htmlify = require('./lib/htmlify.js');

$(document).ready(function() {
  "use strict";
  var child_detail = $('#_proto_detail_panel').removeClass('hidden').detach();
  var linkage_modal = $('#linkage_modal');
  var linkage_list_item = $('.linkage-list-item').detach();
  var maitai_automation_modal = $("#maitai_automation_modal");

  //Add listen for linkage editor
  linkage_modal.on("click", "#linkage_add_new", function(){
    var linkage_list = linkage_modal.find('#linkage_list');
    var new_item = linkage_list_item.clone();
    new_item.data('status', 'new');
    linkage_list.append(new_item);
  });

  linkage_modal.on("click", "#linkage_save", function(){
    var button = $(this);
    var promises = [];
    var deleted = linkage_modal.data('deleted');

    button.prop('disabled', true);

    for(var i = 0; i < deleted.length; i++){
      console.log({method: 'DELETE', url:'/link/' + deleted[i].id + "/"});
      promises.push(
        $.ajax({method: 'DELETE', url:'/link/' + deleted[i].id + "/"})
      );
    }

    var items = linkage_modal.find('.linkage-list-item');

    for(let i = 0; i < items.length; i++){
      var ele = $(items[i]);
      var data = {
        workitem: linkage_modal.find('#linkage_manualcase').val(),
        autocase_pattern: ele.find("#linkage_pattern").val(),
        framework: ele.find("#linkage_framework").val(),
      };
      if(ele.data('status') == 'exists'){
        console.log('PUT', '/link/' + ele.data('linkage').id + "/", JSON.stringify(data));
        promises.push($.ajax({
          contentType: "application/json; charset=utf-8",
          method: 'PUT',
          url:'/link/' + ele.data('linkage').id + "/",
          data: JSON.stringify(data),
        }));
      }
      if(ele.data('status') == 'new'){
        console.log('POST', '/link/', JSON.stringify(data));
        promises.push($.ajax({
          contentType: "application/json; charset=utf-8",
          method: 'POST',
          url:'/link/',
          data: JSON.stringify(data),
        }));
      }
    }

    $.when.apply($, promises).then(function(schemas) {
      linkage_modal.modal('hide');
    }, function(e) {
      alert("Failed to save the linkage data.");
    }).always(function(){
      button.prop('disabled', false);
      $.get('data?pk=' + linkage_modal.find('#linkage_manualcase').val())
        .done(function(data){linkage_modal.data('row').data(data.data[0]).draw();});
    });
  });

  linkage_modal.on("click", "#linkage_delete", function(){
    var linkage_item = $(this).closest(".linkage-list-item");
    var deleted = linkage_modal.data('deleted');
    if (linkage_item.data('linkage') && linkage_item.data('linkage').id) {
        deleted.push(linkage_item.data('linkage'));
    }
    linkage_modal.data('deleted', deleted);
    linkage_item.remove();
  });

  $("#maitai_automation_submit").click(function(){
    var button = $(this);
    var form = maitai_automation_modal.find('form');
    var posting = $.post("/control/maitai_request/", form.serialize());
    button.prop('disabled', true);
    var polarion;
    var rowSelector = function(idx, data, node){
        return data.polarion == polarion;
    };
    posting.done(function(data){
      for(polarion in data){
        var maitai_id = data[polarion].maitai_id;
        var message = data[polarion].message;
        if(maitai_id){
          var row = table.row(rowSelector);
          var d = row.data();
          d.maitai_id = maitai_id;
          table.row(row).data(d).draw(false);
          alert("Maitai create for " + polarion + ", ID: " + maitai_id);
        }
        else{
          alert('Ajax failure for ' + polarion + ': ' + data[polarion].message);
        }
      }
    }).fail(function(jqXHR, textStauts){
      try{
        var data = JSON.stringify(jqXHR.responseText);
        if(data.message){
          alert('Ajax failure: ' + data.message);
        }
        else{
          alert('Ajax failure: ' + jqXHR.responseText);
        }
      }
      catch (e){
        alert('Unknown failure, detail: ' + jqXHR.responseText);
      }
    }).always(function(){
      maitai_automation_modal.modal("hide");
      button.prop('disabled', false);
    });
  });

  var table = $('#sortable-table').DataSearchTable({
    select: true,
    BaseTable: [$.fn.DataTableWithChildRow, $.fn.DataTableWithInlineButton,],
    buttons: [
      {
        text: 'Select All Filted',
        action: function ( e, dt, node, config ) {
          var filterSet = table.$('tr', {filter:'applied'});
          filterSet.each(function(){
            table.row(this).select();
          });
        }
      },
      {
        text: 'Edit Linkage',
        action: function ( e, dt, node, config ) {
          var filterSet = table.$('tr', {selected:true});
          if(filterSet.length > 1){
            alert("Linkage edit with multi-select is not supported yet.");
            return;
          }
          filterSet.each(function(){
            //with select: single, only one row is processed.
            var d = table.row(this).data();
            var linkage_list = linkage_modal.find('#linkage_list').empty();
            linkage_modal.data('deleted', []);
            linkage_modal.data('row', table.row(this));
            $.get("/manual/" + d.polarion + "/link/").done(function(data){
              $.each(data, function(idx, ele){
                var new_item = linkage_list_item.clone();
                new_item.find("#linkage_pattern").val(ele.autocase_pattern);
                new_item.find("#linkage_framework").val(ele.framework);
                new_item.find("#linkage_autocases").html(ele.autocases.join("<br>"));
                new_item.data('linkage', ele);
                new_item.data('status', 'exists');
                linkage_list.append(new_item);
              });
            });
            linkage_modal.find('#linkage_manualcase').val(d.polarion).prop('disabled', true);
            linkage_modal.modal('show');
          });
        }
      },
      {
        text: 'Create Automated Request',
        action: function ( e, dt, node, config ) {
          var filterSet = table.$('tr', {selected:true});
          var caseInput = maitai_automation_modal.find("input[name='manual_cases']");
          var labelInput = maitai_automation_modal.find("input[name='labels']");
          var checkFlag = true;
          caseInput.val('');
          labelInput.val('');
          var count = filterSet.length;
          filterSet.each(function(){
            var row = table.row(this);
            var d = row.data();
            if(d.automation !== "notautomated"){
              alert("Create automation request for a " + d.automation + " is not allowed.");
              checkFlag = false;
              return;
            }
            if(!d.need_automation){
              caseInput.val(caseInput.val() + " " +d.polarion);
              for(let docName of d.documents){
                docName = docName.replace(/\ /g, "");
                if(labelInput.val().indexOf(docName) === -1){
                  labelInput.val((labelInput.val()? "," : "") + docName);
                }
              }
            }
            else{
              alert('Error: ' + d.polarion + ': Maitai pending.');
            }
            if(!--count && checkFlag){
              maitai_automation_modal.modal("show");
            }
          });
        }
      },

    ],
    initComplete: function(){
      var wi_select = $('#linkage_manualcase');
      table.column(function(idx, data, node){
        return $(node).text() == 'Polarion';
      }).data().each(function(d, j){
        wi_select.append('<option value="' + d + '">' + d + '</option>');
      });

      var fr_select = linkage_list_item.find('#linkage_framework');
      $.get("/framework/").done(function(d){
        d = d.results;
        $.each(d, function(idx, d){
          fr_select.append('<option value="' + d.name + '">' + d.name + '</option>');
        });
      });
    },
    "ajax": "data",
    "iDisplayLength": 20,
    "bAutoWidth": false,
    "selectorColumns": [
      {
        column: 'Documents',
        render: htmlify,
      },
      {
        column: 'Automation',
        render: htmlify,
        strict: true,
      },
      {
        column: 'Errors',
        render: htmlify,
      },
    ],
    "columns": [
      {
        "data": "polarion",
        "render": function( data ) {
          return '<a href="https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitem?id='+data+'">'+data+'</a>';
        }
      },
      { "data": "title" },
      {
        "data": "documents",
        "render": function( data ) {
          return htmlify(data.join('\n'));
        }
      },
      { "data": "automation" },
      {
        "data": "errors",
        "render": function( data ) {
          return htmlify(data.join('\n'));
        }
      },
      {
        "data": "cases",
        "visible": false,
        "render": htmlify,
      },
      {
        "data": "patterns",
        "visible": false,
        "render": htmlify,
      },
      {
        "data": "maitai_id",
        "render": htmlify,
      },
      {
        "data": "need_automation",
        "visible": false,
        "render": htmlify,
      },
      {
        "data": "comment",
        "visible": false,
        "render": htmlify,
      },

    ],
    "createdRow": function(row, data, index){
      if(data.errors.length > 0){
        $('td', row).eq(0).addClass('errors');
      }
    },

    // Add event listener for opening and closing details
    childContent: function(row, child, slideDown, slideUp){
      var head = child_detail.clone();
      var d = row.data();

      if(d.cases.length > 0){
        head.find(".detail-autocase").html(d.cases.join("<br>"));
      }
      else{
        head.find(".detail-autocase").closest("tr").remove();
      }

      if(d.errors.length > 0){
        head.find(".detail-error").html(d.errors.join("<br>"));
      }
      else{
        head.find(".detail-error").closest("tr").remove();
      }

      if(d.patterns.length > 0){
        head.find(".detail-pattern").html(d.patterns.join("<br>"));
      }
      else{
        head.find(".detail-pattern").closest("tr").remove();
      }

      if(d.maitai_id){
        head.find(".detail-maitai").html(d.maitai_id);
      }
      else{
        head.find(".detail-maitai").closest("tr").remove();
      }

      if(d.comment){
        head.find(".detail-comment").html(d.comment);
      }
      else{
        head.find(".detail-comment").closest("tr").remove();
      }

      if (d.patterns.length + d.errors.length + d.cases.length === 0 && !d.maitai_id && !d.comment) {
        head.empty().append('<div class="alert alert-info" role="alert">Nothing to show.</div>');
        setTimeout(slideUp, 800);
      }

      child.append(head.html());
      slideDown();
    },
  });
});

