require("./lib/datatables-templates.js");
var htmlify = require('./lib/htmlify.js');
$(document).ready(function() {
  "use strict";
  var table = $('#sortable-table').DataSearchTable( {
    "ajax": "data?type=a2m",
    "iDisplayLength": 20,
    "bAutoWidth": false,
    "selectorColumns": [
      {
        column: 'Component',
        render: htmlify,
      },
      {
        column: 'Framework',
        render: htmlify,
      },
      {
        column: 'Documents',
        render: htmlify,
      },
      {
        column: 'PR',
        render: htmlify,
      },
      {
        column: 'Errors',
        render: htmlify,
      }
    ],
    "columns": [
      { "data": "case" },
      {
        "data": "polarion",
        "render": function(data) {
          var link = "";
          for (var i in data){
            var polarionId = data[i];
            link += '<a href="https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitem?id='+polarionId+'">'+polarionId+'</a><br>';
          }
          return link;
        }
      },
      {
        "data": "title",
        "render": function(data){
          return htmlify(data.join('<br>'));
        }
      },
      {
        "data": "documents",
        "render": function(data){
          return htmlify(data.join('<br>'));
        }
      },
      {
        "data": "components",
        "render": function(data){
          return htmlify(data.join('<br>'));
        }
      },
      {
        "data": "framework",
      },
      {
        "data": "pr",
        "render":  htmlify
      },
      {
        "data": "errors",
        "render": function(data){
          return htmlify(data.join('<br>'));
        }
      },
    ],
    "createdRow": function (row, data, index){
      if (data.errors.length > 0) {
        $('td', row).eq(0).addClass('errors');
      }
    }
  });
});

