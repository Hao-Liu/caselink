var alertAjax = require('../lib/ajaxHelper.js');
var _ = require('lodash');

module.exports = {
  template: "#pattern-matcher",
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
  delimiters: ['${', '}'],
};
