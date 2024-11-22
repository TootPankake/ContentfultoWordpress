<?php
/*
Plugin Name: Brimming - Categories For Pages
Description: Adds categories for pages as well as posts, including their own entry ids.
Version: 1.0
Author: Emre Gumus
*/

function add_metadata_id_to_categories() {
    register_rest_field(
        'category', // The taxonomy to which you want to add the custom field
        'metadata_id', // The name of the custom field in the REST API
        array(
            'get_callback'    => 'get_metadata_id_for_category',
            'update_callback' => 'update_metadata_id_for_category',
            'schema'          => array(
                'description' => __('Metadata ID for the category'),
                'type'        => 'string',
                'context'     => array('view', 'edit'),
            ),
        )
    );
}
add_action('rest_api_init', 'add_metadata_id_to_categories');

// Callback function to get the metadata ID
function get_metadata_id_for_category($object, $field_name, $request) {
    return get_term_meta($object['id'], 'metadata_id', true);
}

// Callback function to update the metadata ID
function update_metadata_id_for_category($value, $object, $field_name) {
    if (!empty($value)) {
        update_term_meta($object->term_id, 'metadata_id', sanitize_text_field($value));
    }
}

// Add a custom column to the category list table
function add_metadata_id_column_category($columns) {
    $columns['metadata_id'] = __('Metadata ID');
    return $columns;
}
add_filter('manage_edit-category_columns', 'add_metadata_id_column_category');

// Populate the custom column with metadata values
function fill_metadata_id_column_category($content, $column_name, $term_id) {
    if ($column_name === 'metadata_id') {
        $metadata_id = get_term_meta($term_id, 'metadata_id', true);
        if (!empty($metadata_id)) {
            $content = esc_attr($metadata_id);
        } else {
            $content = __('No Metadata ID', 'your-text-domain');
        }
    }
    return $content;
}

function custom_rewrite_rules() {
    add_rewrite_rule(
        '^(.+?)/([^/]+)?$',
        'index.php?pagename=$matches[1]&category_name=$matches[2]',
        'top'
    );
}
add_action('init', 'custom_rewrite_rules');
add_filter('manage_category_custom_column', 'fill_metadata_id_column_category', 10, 3);




