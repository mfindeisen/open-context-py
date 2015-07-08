function showCreateItemInterface(type){
	/* shows an interface for creating an item
	 * 
	*/
	var main_modal_title_domID = "myModalLabel";
	var main_modal_body_domID = "myModalBody";
	var title_dom = document.getElementById(main_modal_title_domID);
	var body_dom = document.getElementById(main_modal_body_domID);
	var actInterface = new createItemInterface(type);
	title_dom.innerHTML = actInterface.title;
	body_dom.innerHTML = actInterface.body;
	$("#myModal").modal('show');
}

function createItemInterface(type){
	if (type == 'persons') {
		//make a new persons interface
		this.title = icons.persons;
		this.title += ' Create a New Person or Organization Item';
		this.body = createPersonFields();
	}
	else if (type == 'projects') {
		//make a new persons interface
		this.title = icons.projects;
		this.title += ' Create a New Project or Collection';
		this.body = createProjectFields();
	}
	else if (type == 'profiles') {
		//make a new persons interface
		this.title = icons.profiles;
		this.title += ' Create a New Data Entry Profile';
		this.body = createProfileFields();
	}
}


/*
 *  PERSON / ORGANIZATION CREATION
 *
 */

function createPersonFields(){
	var html = [
	'<div>',
	'<div class="form-group">',
	'<label for="new-item-given-name">Given Name (First Name)</label>',
	'<input id="new-item-given-name" class="form-control input-sm" ',
	'type="text" value="" onchange="person_name_comp();" />',
	'</div>',
	'<div class="form-group">',
	'<label for="new-item-mid-init">Middle Initials</label>',
	'<input id="new-item-mid-init" class="form-control input-sm" style="width:15%;"',
	'type="text" value="" length="5" onchange="person_name_comp();" />',
	'</div>',
	'<div class="form-group">',
	'<label for="new-item-surname">Surname (Family Name)</label>',
	'<input id="new-item-surname" class="form-control input-sm" ',
	'type="text" value="" onchange="person_name_comp();" />',
	'</div>',
	'<div class="form-group">',
	'<label for="new-item-combined-name">Full Name</label>',
	'<input id="new-item-combined-name" class="form-control input-sm" ',
	'type="text" value="" />',
	'</div>',
	'<div class="row" id="new-person-button-row">',
		'<div class="col-xs-4">',
		'<div class="form-group">',
		'<label for="new-item-initials">Initals</label>',
		'<input id="new-item-initials" class="form-control input-sm" style="width:50%;"',
		'type="text" value="" />',
		'</div>',
		'</div>',
		'<div class="col-xs-6">',
		'<label>New Item Type</label><br/>',
		'<label class="radio-inline">',
		'<input type="radio" name="new-item-foaf-type" id="new-item-foaf-type-p" ',
		'class="new-item-foaf-type" value="foaf:Person" checked="checked">',
		'Person </label>',
		'<label class="radio-inline">',
		'<input type="radio" name="new-item-foaf-type" id="new-item-foaf-type-o" ',
		'class="new-item-foaf-type" value="foaf:Organization">',
		'Organization </label>',
		'</div>',
		'<div class="col-xs-2">',
		'<label>Create</label><br/>',
		'<button class="btn btn-default" onclick="createNewPerson();">',
		'<span class="glyphicon glyphicon-plus-sign" aria-hidden="true"></span>',
		' Submit',
		'</button>',
		'</div>',
	'</div>',
	'<div class="row" id="new-person-bottom-row">',
		'<div class="col-xs-4">',
		'<div class="form-group">',
		'<label for="new-item-uuid">UUID for New Person</label>',
		'<input id="new-item-uuid" class="form-control input-sm" ',
		'type="text" value="" placeholder="Mint new UUID" />',
		'</div>',
		'</div>',
		'<div class="col-xs-4">',
		'<div class="form-group">',
		'<label for="new-item-project-uuid">Add Item to Project UUID</label>',
		'<input id="new-item-project-uuid" class="form-control input-sm" ',
		'type="text" value="' + project_uuid + '" />',
		'</div>',
		'</div>',
		'<div class="col-xs-4">',
		'<div class="form-group">',
		'<label for="new-item-project-uuid">Source ID</label>',
		'<input id="new-item-source-id" class="form-control input-sm" ',
		'type="text" value="manual-web-form" />',
		'</div>',
		'</div>',
	'</div>',
	'</div>'
	].join('\n');
	return html;
}


function person_name_comp(){
	var g_name = document.getElementById("new-item-given-name").value;
	var s_name = document.getElementById("new-item-surname").value;
	var m_init = document.getElementById("new-item-mid-init").value;
	var com_dom = document.getElementById("new-item-combined-name");
	var init_dom = document.getElementById("new-item-initials");
	var com_name = [g_name, m_init, s_name].join(' ');
	var initials = g_name.charAt(0) + m_init.replace('.','') + s_name.charAt(0);
	initials = initials.toUpperCase();
	com_name = com_name.replace('  ', ' ');
	com_dom.value = com_name;
	init_dom.value = initials;
}

function createNewPerson(){
	var g_name = document.getElementById("new-item-given-name").value;
	var s_name = document.getElementById("new-item-surname").value;
	var m_init = document.getElementById("new-item-mid-init").value;
	var com_name = document.getElementById("new-item-combined-name").value;
	var initials = document.getElementById("new-item-initials").value;
	var p_types = document.getElementsByClassName("new-item-foaf-type");
	for (var i = 0, length = p_types.length; i < length; i++) {
		if (p_types[i].checked) {
			var foaf_type = p_types[i].value;
		}
	}
	var new_item_uuid = document.getElementById("new-item-uuid").value;
	if (new_item_uuid.length < 1) {
		new_item_uuid = false;
	}
	var new_project_uuid = document.getElementById("new-item-project-uuid").value;
	var new_source_id = document.getElementById("new-item-source-id").value;
	var url = make_url("/edit/create-item-into/") + encodeURIComponent(new_project_uuid);
	var req = $.ajax({
		type: "POST",
		url: url,
		dataType: "json",
		data: {
			uuid: new_item_uuid,
			project_uuid: new_project_uuid,
			item_type: 'persons',
			source_id: new_source_id,
			foaf_type: foaf_type,
			combined_name: com_name,
			given_name: g_name,
			surname: s_name,
			mid_init: m_init,
			initials: initials,
			csrfmiddlewaretoken: csrftoken},
		success: createNewPersonDone,
		error: function (request, status, error) {
			alert('Person creation failed, sadly. Status: ' + status);
		}
	});
}

function createNewPersonDone(data){
	var bottom_row = document.getElementById("new-person-bottom-row");
	bottom_row.innerHTML = '<div class="col-xs-12"> </div>';
	var button_row = document.getElementById("new-person-button-row");
	if (data.change.uuid != false) {
		var url = make_url('/edit/items/' + data.change.uuid)
		var link_html = 'New item: <a target="_blank" ';
		link_html += 'href="' + url + '">';
		link_html += data.change.label + '</a>';
	}
	else{
		var link_html = data.change.label;
	}
	var html = [
	'<div class="col-xs-4">',
	link_html,
	'</div>',
	'<div class="col-xs-8">',
	data.change.note,
	'</div>'
	].join('\n');
	button_row.innerHTML = html;
}


/*
 *  PROJECT CREATION
 *
 */

function createProjectFields(){
	var html = [
	'<div>',
	'<div class="form-group">',
	'<label for="new-item-label">Project Title</label>',
	'<input id="new-item-label" class="form-control input-sm" ',
	'type="text" value="" />',
	'</div>',
	'<div class="form-group">',
	'<label for="new-item-short-des">Short Description (Aim for 140 chars)</label>',
	'<input id="new-item-short-des" class="form-control input-sm" ',
	'type="text" value="" />',
	'</div>',
	'<div class="row">',
	'<div class="col-xs-4" id="new-project-button-container">',
	'<label>Create</label><br/>',
	'<button class="btn btn-default" onclick="createNewProject();">',
	'<span class="glyphicon glyphicon-plus-sign" aria-hidden="true"></span>',
	' Submit',
	'</button>',
	'</div>',
	'<div class="col-xs-8" id="new-project-exp-container">',
	'<p><small>After creating the project, you can add and edit the description / abstract. ',
	'If the project is a sub-project of another project, indicate the parent-project uuid ',
	'below. If the project is a new project without a parent project, make sure the parent-',
	'project uuid is set to: 0</small></p>',
	'</div>',
	'</div>',
	'<div class="row" id="new-project-bottom-row" style="margin-top:20px;">',
		'<div class="col-xs-4">',
		'<div class="form-group">',
		'<label for="new-item-uuid">UUID for New Project</label>',
		'<input id="new-item-uuid" class="form-control input-sm" ',
		'type="text" value="" placeholder="Leave blank to mint a new UUID" />',
		'</div>',
		'</div>',
		'<div class="col-xs-4">',
		'<div class="form-group">',
		'<label for="new-item-project-uuid">Parent-Project UUID (0 for None)</label>',
		'<input id="new-item-project-uuid" class="form-control input-sm" ',
		'type="text" value="' + project_uuid + '" />',
		'</div>',
		'</div>',
		'<div class="col-xs-4">',
		'<div class="form-group">',
		'<label for="new-item-project-uuid">Source ID</label>',
		'<input id="new-item-source-id" class="form-control input-sm" ',
		'type="text" value="manual-web-form" />',
		'</div>',
		'</div>',
	'</div>',
	'</div>'
	].join('\n');
	return html;
}

function createNewProject(){
	var label = document.getElementById("new-item-label").value;
	var short_des = document.getElementById("new-item-short-des").value;
	var new_item_uuid = document.getElementById("new-item-uuid").value;
	if (new_item_uuid.length < 1) {
		new_item_uuid = false;
	}
	var new_project_uuid = document.getElementById("new-item-project-uuid").value;
	var new_source_id = document.getElementById("new-item-source-id").value;
	var url = make_url("/edit/create-project/");
	if (label.length > 0) {
		var req = $.ajax({
			type: "POST",
			url: url,
			dataType: "json",
			data: {
				uuid: new_item_uuid,
				project_uuid: new_project_uuid,
				item_type: 'projects',
				source_id: new_source_id,
				label: label,
				short_des: short_des,
				csrfmiddlewaretoken: csrftoken},
			success: createNewProjectDone,
			error: function (request, status, error) {
				alert('Project creation failed, sadly. Status: ' + request.status);
			} 
		});
	}
	else{
		alert('Please provide a title for this project');
	}
}

function createNewProjectDone(data){
	var button_con = document.getElementById("new-project-button-container");
	if (data.change.uuid != false) {
		var url = make_url('/edit/items/' + data.change.uuid)
		var link_html = 'New item: <a target="_blank" ';
		link_html += 'href="' + url + '">';
		link_html += data.change.label + '</a>';
	}
	else{
		var link_html = data.change.label;
	}
	button_con.innerHTML = '<p>' + link_html + '</p><p><small>' + data.change.note + '</small></p>'; 
}


/*--------------------------------------
 * Create input profile
 *
 ---------------------------------------*/

function createProfileFields(){
	var html = [
	'<div>',
	'<div class="row">',
	'<div class="col-xs-12" style="margin-bottom:10px;">',
		'<label>Profile Item Type</label><br/>',
		'<label class="radio-inline">',
		'<input type="radio" name="new-profile-item-type" id="new-profile-item-type-s" ',
		'class="new-profile-item-type" value="subjects" checked="checked">',
		'Subjects (Locations, objects, etc.) </label>',
		'<label class="radio-inline">',
		'<input type="radio" name="new-profile-item-type" id="new-profile-item-type-m" ',
		'class="new-profile-item-type" value="media">',
		'Media (images, videos, etc.)</label>',
		'<label class="radio-inline">',
		'<input type="radio" name="new-profile-item-type" id="new-profile-item-type-d" ',
		'class="new-profile-item-type" value="documents">',
		'Documents (text diaries, logs, etc.)</label>',
		'</div>',
	'</div>',
	'</div>',
	'<div class="form-group">',
	'<label for="new-item-label">Profile Label</label>',
	'<input id="new-item-label" class="form-control input-sm" ',
	'type="text" value="" />',
	'</div>',
	'<div class="form-group">',
	'<label for="new-item-note">Explanatory Note</label>',
	'<textarea id="new-item-note" class="form-control input-sm" rows="4">',
	'</textarea>',
	'</div>',
	'<div class="row">',
	'<div class="col-xs-4" id="new-profile-button-container">',
	'<label>Create</label><br/>',
	'<button class="btn btn-default" onclick="createNewProfile();">',
	'<span class="glyphicon glyphicon-plus-sign" aria-hidden="true"></span>',
	' Submit',
	'</button>',
	'</div>',
	'<div class="col-xs-8" id="new-profile-exp-container">',
	'<p><small>A data entry profile defines a set of descriptive fields and data validation rules ',
	'for manually creating data. After creating a profile, you can edit it to define fields to use ',
	'in data creation. You can also delete profiles, or duplicate them. ',
	'</small></p>',
	'</div>',
	'</div>',
	'<div class="row" id="new-profile-bottom-row" style="margin-top:20px;">',
		'<div class="col-xs-4">',
		'</div>',
		'<div class="col-xs-4">',
		'<div class="form-group">',
		'<label for="new-item-project-uuid">Project UUID</label>',
		'<input id="new-item-project-uuid" class="form-control input-sm" ',
		'type="text" value="' + project_uuid + '" />',
		'</div>',
		'</div>',
		'<div class="col-xs-4">',
		'</div>',
	'</div>',
	'</div>'
	].join('\n');
	return html;
}

function createNewProfile(){
	var label = document.getElementById("new-item-label").value;
	var note = document.getElementById("new-item-note").value;
	var new_project_uuid = document.getElementById("new-item-project-uuid").value;
	var p_types = document.getElementsByClassName("new-profile-item-type");
	for (var i = 0, length = p_types.length; i < length; i++) {
		if (p_types[i].checked) {
			var item_type = p_types[i].value;
		}
	}
	var url = make_url("/edit/inputs/create-profile/") + encodeURIComponent(new_project_uuid);
	if (label.length > 0) {
		return $.ajax({
			type: "POST",
			url: url,
			dataType: "json",
			data: {
				project_uuid: new_project_uuid,
				item_type: item_type,
				label: label,
				note: note,
				csrfmiddlewaretoken: csrftoken},
			success: createNewProfileDone,
			error: function (request, status, error) {
				alert('Data entry profile creation failed, sadly. Status: ' + request.status);
			} 
		});
	}
	else{
		alert('Please provide a label for this profile');
	}
}

function createNewProfileDone(data){
	var button_con = document.getElementById("new-profile-button-container");
	if (data.change.uuid != false) {
		var url = make_url('/edit/inputs/profiles/' + data.change.uuid + '/edit')
		var link_html = 'New profile: <a target="_blank" ';
		link_html += 'href="' +  url + '">';
		link_html += data.change.label + '</a>';
	}
	else{
		var link_html = data.change.label;
	}
	button_con.innerHTML = '<p>' + link_html + '</p><p><small>' + data.change.note + '</small></p>'; 
}

// this is useful to compose urls for the AJAX requests 
function make_url(relative_url){
	if (typeof base_url != "undefined") {
		return base_url + relative_url;
	}
	else{
		return '../../' + relative_url;
	}
}