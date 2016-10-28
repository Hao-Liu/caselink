var prettier = require('./lib/prettier.js');
$(document).ready(function() {
  require("./lib/datatable_templates.js")
  var table = $('#sortable-table').DataSearchTable( {
    "ajax": "data?type=a2m",
    "iDisplayLength": 20,
    "bAutoWidth": false,
    "selectorColumns": [
      {
        column: 'Component',
        render: prettier,
      },
      {
        column: 'Framework',
        render: prettier,
      },
      {
        column: 'Documents',
        render: prettier,
      },
      {
        column: 'PR',
        render: prettier,
      },
      {
        column: 'Errors',
        render: prettier,
      }
    ],
    "columns": [
      { "data": "case" },
      {
        "data": "polarion",
        "render": function(data) {
          link = ""
          for (i in data){
            polarion_id = data[i];
            link += '<a href="https://polarion.engineering.redhat.com/polarion/#/project/RedHatEnterpriseLinux7/workitem?id='+polarion_id+'">'+polarion_id+'</a><br>';
          }
          return link;
        }
      },
      {
        "data": "title",
        "render": function(data){
          return prettier(data.join('<br>'));
        }
      },
      {
        "data": "documents",
        "render": function(data){
          return prettier(data.join('<br>'));
        }
      },
      {
        "data": "components",
        "render": function(data){
          return prettier(data.join('<br>'));
        }
      },
      {
        "data": "framework",
      },
      {
        "data": "pr",
        "render":  prettier
      },
      {
        "data": "errors",
        "render": function(data){
          return prettier(data.join('<br>'));
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

