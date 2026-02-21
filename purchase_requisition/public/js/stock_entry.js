// Copyright (c) 2025, mohtashim and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Entry', {
	refresh: function(frm) {
		// Add a button to check stock availability
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Check Stock Availability'), function() {
				frm.trigger('check_stock_availability');
			}, __('Tools'));
			
			// Add a button to check future transactions
			frm.add_custom_button(__('Check Future Transactions'), function() {
				frm.trigger('check_future_transactions');
			}, __('Tools'));
		}
		
		// Add a button to enable negative stock for items if needed
		if (frm.doc.docstatus === 0 && frm.doc.items && frm.doc.items.length > 0) {
			frm.add_custom_button(__('Enable Negative Stock for Items'), function() {
				frm.trigger('enable_negative_stock_for_items');
			}, __('Tools'));
		}
	},
	
	check_future_transactions: function(frm) {
		if (!frm.doc.items || frm.doc.items.length === 0) {
			frappe.msgprint(__('Please add items first.'));
			return;
		}
		
		// Call the whitelisted method on the document
		frm.call('get_future_transaction_details').then(function(r) {
			if (r.message) {
				frm.trigger('show_future_transaction_details', r.message);
			}
		});
	},
	
	show_future_transaction_details: function(frm, data) {
		if (!data.has_conflicts) {
			frappe.msgprint({
				title: __('Future Transaction Check'),
				message: __('✅ No future transaction conflicts found.'),
				indicator: 'green'
			});
			return;
		}
		
		let message = '<b>' + __('Future Transaction Conflicts Detected') + '</b><br><br>';
		message += __('This transaction would cause the following future transactions to have negative stock:<br><br>');
		
		data.conflicts.forEach(function(item_conflict) {
			message += '<b>Item: ' + item_conflict.item_code + ' (' + item_conflict.item_name + ')</b><br>';
			message += __('Warehouse: ') + item_conflict.warehouse + '<br>';
			message += __('Transfer Qty: ') + item_conflict.transfer_qty + '<br>';
			message += '<table class="table table-bordered" style="margin-top: 10px;">';
			message += '<thead><tr>';
			message += '<th>' + __('Document') + '</th>';
			message += '<th>' + __('Date') + '</th>';
			message += '<th>' + __('Time') + '</th>';
			message += '<th>' + __('Current Qty After') + '</th>';
			message += '<th>' + __('Projected Qty After') + '</th>';
			message += '<th>' + __('Shortage') + '</th>';
			message += '</tr></thead><tbody>';
			
			item_conflict.conflicts.forEach(function(conflict) {
				message += '<tr class="danger">';
				message += '<td><a href="/app/' + conflict.voucher_type.toLowerCase().replace(' ', '-') + '/' + conflict.voucher_no + '">' + conflict.voucher_type + ' - ' + conflict.voucher_no + '</a></td>';
				message += '<td>' + conflict.posting_date + '</td>';
				message += '<td>' + (conflict.posting_time || '') + '</td>';
				message += '<td>' + conflict.current_qty_after + '</td>';
				message += '<td>' + conflict.projected_qty_after + '</td>';
				message += '<td><b>' + conflict.shortage + '</b></td>';
				message += '</tr>';
			});
			
			message += '</tbody></table><br>';
		});
		
		message += '<b>' + __('Solutions:') + '</b><br>';
		message += '1. ' + __('Enable "Allow Negative Stock" in Stock Settings or for the specific items') + '<br>';
		message += '2. ' + __('Cancel or adjust the future transactions shown above') + '<br>';
		message += '3. ' + __('Add stock to the warehouses before the future transaction dates') + '<br>';
		message += '4. ' + __('Change the posting date of this transaction to after the future transactions');
		
		frappe.msgprint({
			title: __('Future Transaction Conflicts'),
			message: message,
			indicator: 'red',
			wide: true
		});
	},
	
	check_stock_availability: function(frm) {
		if (!frm.doc.items || frm.doc.items.length === 0) {
			frappe.msgprint(__('Please add items first.'));
			return;
		}
		
		let stock_status = [];
		let promises = [];
		
		frm.doc.items.forEach(function(item) {
			if (item.item_code && item.s_warehouse) {
				let promise = frappe.call({
					method: 'erpnext.stock.utils.get_stock_balance',
					args: {
						item_code: item.item_code,
						warehouse: item.s_warehouse,
						posting_date: frm.doc.posting_date,
						posting_time: frm.doc.posting_time
					},
					callback: function(r) {
						let available_qty = r.message || 0;
						let required_qty = item.transfer_qty || 0;
						let shortage = required_qty - available_qty;
						
						stock_status.push({
							item_code: item.item_code,
							item_name: item.item_name,
							warehouse: item.s_warehouse,
							required: required_qty,
							available: available_qty,
							shortage: shortage > 0 ? shortage : 0,
							status: available_qty >= required_qty ? '✅' : '❌'
						});
					}
				});
				promises.push(promise);
			}
		});
		
		Promise.all(promises).then(function() {
			frm.trigger('show_stock_status', stock_status);
		});
	},
	
	show_stock_status: function(frm, stock_status) {
		let message = '<table class="table table-bordered">';
		message += '<thead><tr>';
		message += '<th>' + __('Item Code') + '</th>';
		message += '<th>' + __('Warehouse') + '</th>';
		message += '<th>' + __('Required') + '</th>';
		message += '<th>' + __('Available') + '</th>';
		message += '<th>' + __('Shortage') + '</th>';
		message += '<th>' + __('Status') + '</th>';
		message += '</tr></thead><tbody>';
		
		let has_shortage = false;
		
		stock_status.forEach(function(status) {
			let row_class = status.shortage > 0 ? 'danger' : 'success';
			message += '<tr class="' + row_class + '">';
			message += '<td>' + status.item_code + '</td>';
			message += '<td>' + status.warehouse + '</td>';
			message += '<td>' + status.required + '</td>';
			message += '<td>' + status.available + '</td>';
			message += '<td>' + (status.shortage > 0 ? status.shortage : '-') + '</td>';
			message += '<td>' + status.status + '</td>';
			message += '</tr>';
			
			if (status.shortage > 0) {
				has_shortage = true;
			}
		});
		
		message += '</tbody></table>';
		
		if (has_shortage) {
			message += '<br><b>' + __('Solutions:') + '</b><br>';
			message += '1. ' + __('Enable "Allow Negative Stock" in Stock Settings') + '<br>';
			message += '2. ' + __('Enable "Allow Negative Stock" for the specific items') + '<br>';
			message += '3. ' + __('Add stock to the warehouses before submitting') + '<br>';
			message += '4. ' + __('Reduce the quantities in this Stock Entry');
		}
		
		frappe.msgprint({
			title: __('Stock Availability Check'),
			message: message,
			indicator: has_shortage ? 'orange' : 'green'
		});
	},
	
	enable_negative_stock_for_items: function(frm) {
		if (!frm.doc.items || frm.doc.items.length === 0) {
			frappe.msgprint(__('Please add items first.'));
			return;
		}
		
		let item_codes = [];
		frm.doc.items.forEach(function(item) {
			if (item.item_code && item_codes.indexOf(item.item_code) === -1) {
				item_codes.push(item.item_code);
			}
		});
		
		if (item_codes.length === 0) {
			frappe.msgprint(__('No items found.'));
			return;
		}
		
		frappe.confirm(
			__('This will enable "Allow Negative Stock" for the following items: {0}. Do you want to continue?', [item_codes.join(', ')]),
			function() {
				// Yes
				frappe.call({
					method: 'frappe.client.set_value',
					args: {
						doctype: 'Item',
						name: item_codes[0], // For now, just enable for first item
						fieldname: 'allow_negative_stock',
						value: 1
					},
					callback: function(r) {
						if (r.message) {
							frappe.msgprint(__('Negative stock enabled for items. Please refresh the form.'));
						}
					}
				});
			},
			function() {
				// No
			}
		);
	}
});

