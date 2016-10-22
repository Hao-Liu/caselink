(
    function(root, $){
        var _caselinkURL = "/caselink/api";

        class CaseLinkItem {
            _ajaxHelper(method, data){
                return $.ajax({
                    method: method,
                    url: this.url,
                    data: JSON.stringify(data),
                }).fail(function(jqXHR, textStatus, errorThrown){
                    if(jqXHR.status == 404)
                        this.exists = false;
                    else
                        throw errorThrown;
                });
            }
            constructor(param){
                if(!this.type || !this.id){
                    throw "Subclass's constructor need to set type and id."
                }
                this.exists = false;
                this.url = _caselinkURL + "/" + this.type + "/" + this.id;
                return _ajaxHelper('GET').done(function(data){
                    this._caselinkObject = data;
                    this.exists = true;
                });
            }
            delete(){
                return _ajaxHelper('DELETE').done(function(){
                    this.exists = false;
                });
            }
            save(){
                if(this.exists){
                    return _ajaxHelper('PUT', this._caselinkObject);
                }
                else{
                    return _ajaxHelper('POST', this._caselinkObject).done(function(){
                        this.exists = true;
                    });
                }
            }
            get CaseLinkObject(){
                if(this.exists){
                    return this._caselinkObject;
                } else {
                    this._caselinkObject = {};
                    return this._caselinkObject;
                }
            }
        }

        class AutoCase extends CaseLinkItem {
            constructor(param){
                this.type = 'auto';
                this.id = this._caselinkObject.case;
                super();
            }
        }

        class ManualCase extends CaseLinkItem {
            constructor(){
                this.type = 'manual';
                this.id = this._caselinkObject.id;
                super();
            }
        }

        class Linkage extends CaseLinkItem {
            constructor(){
                this.type = 'link';
                this.id = this._caselinkObject.id;
                super();
            }
        }

        class AutoCaseFailure extends CaseLinkItem {
            constructor(){
                this.type = 'failure';
                this.id = this._caselinkObject.id;
                super();
            }
        }

        class Bug extends CaseLinkItem {
            constructor(){
                this.type = 'bug';
                this.id = this._caselinkObject.id;
                super();
            }
        }

        root.Linkage = Linkage;
    }(this, $)
)
