//Use a mixin to make use of bootstrap components.
var taskPanel = require("../components/task-panel.js");
var patternMatcher = require("../components/pattern-matcher.js");

module.exports = {
  data: {
    showTaskPanel: false,
    showPatternMatcher: false,
  },
  components: {
    'task-panel': taskPanel,
    'pattern-matcher': patternMatcher,
  },
  methods: {
  },
  mounted: function(){
    var that = this;
    $("#task-panel-modal").on('hidden.bs.modal', function (e) {
      that.showTaskPanel = false;
    });
    $('#task-panel-modal').on('show.bs.modal', function (e) {
      that.showTaskPanel = true;
    });
  },
  delimiters: ['${', '}'],
};
